from __future__ import annotations
# mahjong.py — 16 張麻將模擬器（Python 重構版）
# 原始實作：mahjong.go（Go 語言）

# ---------------------------------------------------------------------------
# 牌面常數
# ---------------------------------------------------------------------------

TILES_PER_SUIT = 9      # 每種數牌的點數數量（1–9）
SUIT_COUNT = 3          # 數牌種類數（筒/索/萬）
COPIES = 4              # 每張牌的副本數
WIND_COUNT = 4          # 風牌種類數（東南西北）
DRAGON_COUNT = 3        # 三元牌種類數（中發白）
BONUS_COUNT = 8         # 花牌數量（春夏秋冬梅蘭菊竹）

# 各牌型起始索引（以整數牌號計算）
SUITED_START = 0
SUITED_END = SUIT_COUNT * TILES_PER_SUIT * COPIES          # 108
WIND_START = SUITED_END                                     # 108
WIND_END = WIND_START + WIND_COUNT * COPIES                 # 124
DRAGON_START = WIND_END                                     # 124
DRAGON_END = DRAGON_START + DRAGON_COUNT * COPIES           # 136
BONUS_START = DRAGON_END                                    # 136
TOTAL_TILES = BONUS_START + BONUS_COUNT                     # 144

# 每種「牌面」數量（去副本後）
SUITED_KINDS = SUIT_COUNT * TILES_PER_SUIT                  # 27
WIND_KINDS = WIND_COUNT                                     # 4
DRAGON_KINDS = DRAGON_COUNT                                 # 3
HONOR_KINDS = WIND_KINDS + DRAGON_KINDS                     # 7（字牌合計）

_SUIT_NAMES = ["筒", "索", "萬"]
_WIND_NAMES = ["東", "南", "西", "北"]
_DRAGON_NAMES = ["中", "發", "白"]
_BONUS_NAMES = ["春", "夏", "秋", "冬", "梅", "蘭", "菊", "竹"]


def n_to_chinese(n: int) -> str:
    """將牌號整數轉換為對應的中文牌名。

    牌號對應規則：
    - 0–107：數牌（筒/索/萬，每種 36 張）
    - 108–123：風牌（東南西北，各 4 張）
    - 124–135：三元牌（中發白，各 4 張）
    - 136–143：花牌（春夏秋冬梅蘭菊竹，各 1 張）

    Args:
        n: 牌號整數（0 至 TOTAL_TILES - 1）

    Returns:
        對應的中文牌名字串，無效牌號回傳 "？"
    """
    if n < 0 or n >= TOTAL_TILES:
        return "？"
    if n < SUITED_END:
        kind = n // COPIES                          # 牌面種類索引 0–26
        suit = kind // TILES_PER_SUIT               # 0=筒, 1=索, 2=萬
        rank = kind % TILES_PER_SUIT + 1            # 1–9
        return f"{rank}{_SUIT_NAMES[suit]}"
    if n < WIND_END:
        idx = (n - WIND_START) // COPIES
        return _WIND_NAMES[idx]
    if n < DRAGON_END:
        idx = (n - DRAGON_START) // COPIES
        return _DRAGON_NAMES[idx]
    return _BONUS_NAMES[n - BONUS_START]


# ---------------------------------------------------------------------------
# 資料結構
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass
class PlayerState:
    """單一玩家的遊戲狀態。

    Attributes:
        hand: 手牌列表，長度為 n_hand（不含剛摸入的牌）
        table: 已亮出的花牌列表
        seen: 索引為牌面種類（tile // COPIES），記錄各牌面已出現張數
    """
    n_hand: int
    hand: list[int] = field(default_factory=list)
    table: list[int] = field(default_factory=list)
    seen: list[int] = field(default_factory=lambda: [0] * (SUITED_KINDS + HONOR_KINDS))

    def add_seen(self, tile: int) -> None:
        """記錄某張牌已出現（包含自己摸到或他人打出）。

        Args:
            tile: 牌號整數
        """
        kind = tile // COPIES
        if kind < len(self.seen):
            self.seen[kind] += 1


@dataclass
class AIContext:
    """AI 決策所需的輔助資料，與遊戲狀態分離。

    Attributes:
        gates: 打出某張牌後的聽牌候選，key 為牌號，value 為聽牌數
        play_freq: 各手牌位置的「已出現張數」（出現越多代表越容易打掉）
    """
    gates: dict[int, int] = field(default_factory=dict)
    play_freq: dict[int, int] = field(default_factory=dict)


@dataclass
class Mahjong:
    """麻將遊戲狀態，管理牌堆與四位玩家。

    Attributes:
        n_hand: 每位玩家起始手牌數（預設 16）
        remain: 剩餘待摸牌堆
        sea: 棄牌海底（所有玩家打出的牌）
        players: 四位玩家的遊戲狀態
        ai: 四位玩家的 AI 決策資料
    """
    n_hand: int = 16
    remain: list[int] = field(default_factory=list)
    sea: list[int] = field(default_factory=list)
    players: list[PlayerState] = field(default_factory=list)
    ai: list[AIContext] = field(default_factory=list)

    def __post_init__(self) -> None:
        """初始化四位玩家的狀態與 AI 資料。"""
        if not self.players:
            self.players = [PlayerState(n_hand=self.n_hand) for _ in range(4)]
        if not self.ai:
            self.ai = [AIContext() for _ in range(4)]

    def deal_one(self) -> int:
        """從牌堆取出最上方一張牌並回傳。

        Returns:
            牌號整數；若牌堆已空則回傳 -1
        """
        if not self.remain:
            return -1
        tile = self.remain[0]
        self.remain = self.remain[1:]
        return tile

    def _draw_bonus(self, p: PlayerState, idx: int) -> None:
        """若 hand[idx] 為花牌，持續補牌直到摸到非花牌。

        補到的花牌移至 p.table；若牌堆已空則停止。

        Args:
            p:   玩家狀態
            idx: 手牌中需要檢查的位置索引
        """
        while p.hand[idx] >= BONUS_START:
            p.table.append(p.hand[idx])
            next_tile = self.deal_one()
            if next_tile < 0:
                return
            print(f"補 {n_to_chinese(next_tile)}", end="")
            p.hand[idx] = next_tile

    def init_deal(self) -> None:
        """洗牌並輪流發 n_hand 張牌給四位玩家。

        使用 random.sample 產生隨機排列的完整牌堆，
        再以輪流方式（玩家 0→1→2→3→0→…）逐張發牌。
        """
        import random
        self.remain = random.sample(range(TOTAL_TILES), TOTAL_TILES)
        for i in range(self.n_hand):
            for j in range(4):
                p = self.players[j]
                p.hand.append(self.deal_one())

    def show_bonus(self) -> None:
        """初始發牌後，對四位玩家補花並初始化見牌統計。

        補花結束後呼叫 p.add_seen() 將初始手牌計入見牌紀錄，
        代表這些牌不會再從牌堆摸到。
        """
        for player_idx in range(4):
            p = self.players[player_idx]
            print(f"\n{player_idx}", end="")
            for i in range(p.n_hand):
                print(f" {n_to_chinese(p.hand[i])}", end="")
                self._draw_bonus(p, i)
            for tile in p.hand:
                p.add_seen(tile)


# ---------------------------------------------------------------------------
# 快速驗收（執行此模組時顯示）
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        (0, "1筒"),
        (3, "1筒"),
        (4, "2筒"),
        (35, "9筒"),
        (36, "1索"),
        (72, "1萬"),
        (107, "9萬"),
        (108, "東"),
        (120, "北"),
        (124, "中"),
        (132, "白"),
        (136, "春"),
        (143, "竹"),
    ]
    all_pass = True
    for tile_id, expected in tests:
        result = n_to_chinese(tile_id)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_pass = False
        print(f"  {status} n_to_chinese({tile_id:3d}) = {result!r:6s}  (預期 {expected!r})")
    print()
    print("全部通過 ✓" if all_pass else "有測試失敗 ✗")

    print("\n--- 資料結構驗收 ---")
    m = Mahjong(n_hand=16)
    assert len(m.players) == 4, "玩家數應為 4"
    assert len(m.ai) == 4, "AI 資料數應為 4"
    for p in m.players:
        assert p.n_hand == 16
        assert p.hand == []
        assert p.table == []
        assert len(p.seen) == SUITED_KINDS + HONOR_KINDS
    p0 = m.players[0]
    p0.add_seen(0)
    assert p0.seen[0] == 1, "add_seen 應更新 seen[0]"
    print("  ✓ PlayerState 初始化正確")
    print("  ✓ AIContext 初始化正確")
    print("  ✓ Mahjong.__post_init__ 正確建立四位玩家")
    print("  ✓ add_seen() 運作正常")

    print("\n--- 發牌與花牌補牌驗收 ---")
    import random
    random.seed(42)
    m2 = Mahjong(n_hand=16)
    m2.init_deal()
    for i, p in enumerate(m2.players):
        assert len(p.hand) == 16, f"玩家 {i} 手牌數應為 16，實際 {len(p.hand)}"
    print("  ✓ init_deal() 後每位玩家恰有 16 張牌")

    m2.show_bonus()
    print()
    for i, p in enumerate(m2.players):
        for tile in p.hand:
            assert tile < BONUS_START, f"玩家 {i} 手牌 {tile} 不應為花牌"
    print("  ✓ show_bonus() 後手牌中無花牌")

    for i, p in enumerate(m2.players):
        total_seen = sum(p.seen)
        assert total_seen == 16, f"玩家 {i} seen 合計應為 16，實際 {total_seen}"
    print("  ✓ show_bonus() 後 seen 正確初始化（合計 16）")
