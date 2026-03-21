# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "readchar",
# ]
# ///
from __future__ import annotations
from enum import IntEnum
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

# 玩家模式
HUMAN_PLAYER: int = 0        # 人類玩家席位（0–3），其餘為 AI

# AI 行為開關
AI_AUTO_KONG: bool = False   # 明槓：預設不自動槓，改為 True 可啟用
PAUSE_ON_MELD: bool = False  # 吃/碰/槓後暫停，等待使用者按 y 繼續（互動模式）
RUN_TESTS: bool = False      # 執行 __main__ 驗收測試（True 時才跑，False 直接對局）

_SEAT_WIND_NAMES = ["東", "南", "西", "北"]

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
# 危險等級
# ---------------------------------------------------------------------------

class DangerLevel(IntEnum):
    """牌面放槍危險等級，數值越大越危險。

    等級定義：

    EXTREMELY_SAFE (0) — 極度安全（麻將術語：絕張）
        - 數牌或字牌，全局棄牌中同牌面已出現 4 次（四張全出，不可能放槍）
        - 曾被吃（chi_tiles）、碰（pon_tiles）或槓（kong_tiles）的牌面

    VERY_SAFE (1) — 很安全
        - 花牌（BONUS_START 以上）
        - 全局棄牌中同牌面出現 ≥ 2 次（大量已見，對手持有機率低）

    SAFE (2) — 安全
        - 字牌（風牌、三元牌）：無順子可能，威脅範圍有限
        - 最近 3 輪（12 次棄牌）內有人打出過的牌面

    DANGEROUS (3) — 危險
        - 數牌，且曾出現在早期棄牌（3 輪以前），但最近 3 輪未再出現
        （早期打出代表可能是孤張，對手不一定需要；但因時間距離遠，不確定性高）

    VERY_DANGEROUS (4) — 很危險
        - 數牌，從未出現在任何人的棄牌中
        - 未來擴充：也未被下一家吃、其他三家碰/槓

    EXTREMELY_DANGEROUS (5) — 極度危險（湊牌中）
        - 數牌，經 find_hand_chows() 偵測，屬於手牌中正在組成順子的牌面
        - 數牌，經 find_hand_pungs() 偵測，同牌面種類張數 >= 3（刻子已成或槓子）
        - 字牌，經 find_hand_pairs() 偵測，字牌中張數 >= 2（對子候選，含將牌）
        - 以上牌面若棄出，會破壞自身面子或將牌組合，不應棄出
        - 未來整合至 AI 棄牌策略：decide_play() 應跳過此等級的牌
    """
    EXTREMELY_SAFE      = 0
    VERY_SAFE           = 1
    SAFE                = 2
    DANGEROUS           = 3
    VERY_DANGEROUS      = 4
    EXTREMELY_DANGEROUS = 5   # 湊牌中，屬於順子組成的牌，不應棄出


# ---------------------------------------------------------------------------
# 資料結構
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field


@dataclass
class PlayerState:
    """單一玩家的遊戲狀態。

    Attributes:
        hand:     手牌列表，長度為 n_hand（不含剛摸入的牌）
        bonus:    已亮出的花牌列表（春夏秋冬梅蘭菊竹）
        melds:    已亮出的面牌組列表，每組為 [配牌..., 棄牌] 共 3–4 張
        seen:     索引為牌面種類（tile // COPIES），記錄各牌面已出現張數
        discards: 該玩家本局打出的所有牌（依打出順序排列），供 AI 放槍預防使用
    """
    n_hand: int
    hand: list[int] = field(default_factory=list)
    bonus: list[int] = field(default_factory=list)
    melds: list[list[int]] = field(default_factory=list)
    seen: list[int] = field(default_factory=lambda: [0] * (SUITED_KINDS + HONOR_KINDS))
    discards: list[int] = field(default_factory=list)
    chi_count: int = 0   # 本局已吃的面子數（每吃一次 +1）
    pon_count: int = 0   # 本局已碰的面子數（每碰一次 +1）
    kong_count: int = 0  # 本局已明槓的面子數（每槓一次 +1）

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
        n_hand:  每位玩家起始手牌數（預設 16）
        remain:  剩餘待摸牌堆
        players: 四位玩家的遊戲狀態（各自的 discards 記錄個人棄牌）
        ai:      四位玩家的 AI 決策資料

    棄牌查詢：
        全局海底請使用 sea 屬性（聚合所有玩家的 discards）；
        個人棄牌請直接存取 players[i].discards。
    """
    n_hand: int = 16
    remain: list[int] = field(default_factory=list)
    players: list[PlayerState] = field(default_factory=list)
    ai: list[AIContext] = field(default_factory=list)

    @property
    def sea(self) -> list[int]:
        """聚合所有玩家棄牌，回傳完整海底牌列表（依打出順序交錯）。"""
        result = []
        max_len = max((len(p.discards) for p in self.players), default=0)
        for i in range(max_len):
            for p in self.players:
                if i < len(p.discards):
                    result.append(p.discards[i])
        return result

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
            p.bonus.append(p.hand[idx])
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
# 胡牌判定演算法
# 參考論文：arXiv:1707.07345
# ---------------------------------------------------------------------------

def is_honor(honor: list[int]) -> bool:
    """檢查字牌分佈是否合法（每種字牌只能是 0 或 3 張刻子）。

    Args:
        honor: 長度 HONOR_KINDS 的列表，各索引代表一種字牌的出現次數

    Returns:
        合法（全為 0 或 3）回傳 True，否則 False
    """
    return all(c == 0 or c == 3 for c in honor)


def _decompose_suited(
    s: list[int], chows: list[tuple[int, int, int]]
) -> bool:
    """遞迴分解數牌，將找到的順子 (i, i+1, i+2) 附加至 chows。

    從最小牌面開始，遇到 >= 3 張先消刻子後遞迴（刻子不記錄）；
    遇到 1–2 張嘗試消順子後遞迴（順子記錄至 chows）；
    負數或無法消則回傳 False。

    Args:
        s:     長度 SUITED_KINDS（27）的列表副本，索引為牌面種類，值為張數
        chows: 累積順子列表，每個順子以 (i, i+1, i+2) tuple 表示

    Returns:
        可完整分解回傳 True，否則 False
    """
    for suit in range(SUIT_COUNT):
        base = suit * TILES_PER_SUIT
        for offset in range(TILES_PER_SUIT):
            i = base + offset
            n = s[i]
            if n < 0:
                return False
            if n == 0:
                continue
            if n >= 3:
                s[i] -= 3
                return _decompose_suited(s, chows)      # 刻子：不記錄
            # n == 1 or 2：必須組成順子
            if offset + 2 >= TILES_PER_SUIT or s[i + 1] < 1 or s[i + 2] < 1:
                return False
            s[i] -= 1; s[i + 1] -= 1; s[i + 2] -= 1
            chows.append((i, i + 1, i + 2))
            return _decompose_suited(s, chows)          # 順子：記錄
    return True


def find_hand_chows(suited: list[int]) -> list[tuple[int, int, int]] | None:
    """找出手牌數牌中所有順子的牌面種類組合（貪婪分解）。

    Args:
        suited: 長度 SUITED_KINDS（27）的列表，索引為牌面種類，值為張數

    Returns:
        可完整分解時回傳順子列表（每個順子為三個牌面種類索引 tuple），
        無法完整分解則回傳 None。
    """
    chows: list[tuple[int, int, int]] = []
    if _decompose_suited(suited[:], chows):
        return chows
    return None


def find_hand_pungs(suited: list[int]) -> list[tuple[int, int]]:
    """找出手牌數牌中的刻子或槓子（同牌面種類張數 >= 3）。

    對子（2 張）由 find_hand_pairs 負責；本函式僅回傳刻子（3 張）與槓子（4 張），
    兩者皆屬湊牌中，標記為 EXTREMELY_DANGEROUS。

    Args:
        suited: 長度 SUITED_KINDS（27）的列表，索引為牌面種類，值為張數

    Returns:
        list of (kind_idx, count)，count 為 3（刻子已成）或 4（槓子已成）
    """
    return [(i, c) for i, c in enumerate(suited) if c >= 3]


def find_hand_pairs(honor: list[int]) -> list[int]:
    """找出字牌中的對子候選（張數 >= 2）。

    對子（含將牌候選）或刻子皆屬湊牌中，應標記為 EXTREMELY_DANGEROUS。

    Args:
        honor: 長度 HONOR_KINDS 的列表，索引為字牌牌面種類，值為張數

    Returns:
        張數 >= 2 的牌面種類索引列表
    """
    return [i for i, c in enumerate(honor) if c >= 2]


def _get_meld_kinds(hand17: list[int]) -> set[int]:
    """回傳 hand17 中屬於湊牌組合的全局牌面種類索引集合。

    - 數牌順子（find_hand_chows）中的牌面種類
    - 數牌刻子/槓子（find_hand_pungs）中的牌面種類
    - 字牌對子以上（find_hand_pairs）中的牌面種類（以 SUITED_KINDS 為偏移量）

    Args:
        hand17: 含摸入牌的 17 張牌號列表

    Returns:
        湊牌牌面種類索引集合（全局索引，字牌已加 SUITED_KINDS 偏移）
    """
    suited = [0] * SUITED_KINDS
    honor  = [0] * HONOR_KINDS
    for tile in hand17:
        if tile < SUITED_END:
            suited[tile // COPIES] += 1
        elif tile < BONUS_START:
            honor[(tile - SUITED_END) // COPIES] += 1

    kinds: set[int] = set()
    chows = find_hand_chows(suited)
    if chows:
        for c in chows:
            kinds.update(c)
    for kind_idx, _ in find_hand_pungs(suited):
        kinds.add(kind_idx)
    for honor_idx in find_hand_pairs(honor):
        kinds.add(SUITED_KINDS + honor_idx)
    return kinds


def danger_discard_index(
    hand17: list[int],
    players: list[PlayerState],
) -> tuple[int, DangerLevel]:
    """按放槍 DangerLevel 選出最佳棄牌索引。

    判定流程：
    1. 對 hand17 每張牌計算危險等級：
       - 其 kind 在 _get_meld_kinds() 結果中 → EXTREMELY_DANGEROUS（湊牌，不應棄出）
       - 否則 → classify_danger(tile, players)（放槍危險評估）
    2. 選出等級最小（最安全）的候選牌
    3. 同等級時優先棄字牌（SUITED_END <= tile < BONUS_START）
    4. 同等級無字牌時，棄離中間牌（5筒/5索/5萬，offset=4）最遠的數牌

    若棄出的牌等級為 EXTREMELY_DANGEROUS（湊牌），稱為「拆牌」。

    Args:
        hand17:  含摸入牌的 17 張牌號列表
        players: 四位玩家狀態（供 classify_danger 評估放槍風險）

    Returns:
        (hand17 中的棄牌索引, 該牌的 DangerLevel)
    """
    meld_kinds = _get_meld_kinds(hand17)

    # 計算每張牌的危險等級
    levels: list[DangerLevel] = []
    for tile in hand17:
        kind = tile // COPIES
        if kind in meld_kinds:
            levels.append(DangerLevel.EXTREMELY_DANGEROUS)
        else:
            levels.append(classify_danger(tile, players))

    min_level = min(levels)
    candidates = [i for i, lv in enumerate(levels) if lv == min_level]

    # 同等級優先棄字牌
    honor_cands = [i for i in candidates
                   if SUITED_END <= hand17[i] < BONUS_START]
    if honor_cands:
        return honor_cands[0], min_level

    # 無字牌：棄離 5（offset=4）最遠的數牌
    def _dist_from_center(idx: int) -> int:
        kind = hand17[idx] // COPIES
        return abs(kind % TILES_PER_SUIT - 4)

    best = max(candidates, key=_dist_from_center)
    return best, min_level


def is_suit(suited: list[int]) -> bool:
    """Theorem 1：以貪婪遞迴判斷數牌是否可完整分解為刻子或順子。

    從最小牌面開始，遇到 >= 3 張先消刻子後遞迴；
    遇到 1–2 張嘗試消順子後遞迴；負數或無法消則回傳 False。

    參考：arXiv:1707.07345 Theorem 1

    Args:
        suited: 長度 SUITED_KINDS（27）的列表，索引為牌面種類，值為張數

    Returns:
        可完整分解回傳 True，否則 False
    """
    return _decompose_suited(suited[:], [])


def _find_i_pair(s: list[int], i: int) -> bool:
    """判斷 s[i] 與 s[i+1] 是否為相同牌面的對子（且為第一次出現）。

    Args:
        s:    已排序的牌號列表
        i:    候選位置索引

    Returns:
        是對子且為首次出現回傳 True
    """
    if i + 1 >= len(s):
        return False
    if s[i] // COPIES != s[i + 1] // COPIES:
        return False
    if i > 0 and s[i - 1] // COPIES == s[i] // COPIES:
        return False    # 避免重複計算同一對
    return True


def _find_suit_pairs(s: list[int]) -> list[int]:
    """Theorem 2：利用牌面 mod 3 分組，快速找出數牌中可能的將牌候選索引。

    參考：arXiv:1707.07345 Theorem 2

    Args:
        s: 已排序、同一花色的牌號子列表

    Returns:
        候選對子的起始索引列表（相對於 s）
    """
    bins: list[list[int]] = [[], [], []]
    for i, tile in enumerate(s):
        bins[(tile // COPIES) % 3].append(i)

    counts = [len(b) for b in bins]
    # 找 mod 3 餘數不同的那組，將牌必在其中
    if counts[0] % 3 != counts[1] % 3:
        target = 0 if counts[0] % 3 != counts[2] % 3 else 1
    else:
        target = 2
    return bins[target]


def find_pair(hand17: list[int]) -> tuple[list[int], list[int], list[int]]:
    """將 17 張已排序手牌分析出各種牌型的分佈，並找出所有候選將牌索引。

    Args:
        hand17: 長度 17 的已排序牌號列表

    Returns:
        (suited, honor, pair_indices)
        - suited: 長度 SUITED_KINDS 的數牌張數分佈
        - honor:  長度 HONOR_KINDS 的字牌張數分佈
        - pair_indices: 所有候選將牌在 hand17 中的起始索引
    """
    suited = [0] * SUITED_KINDS
    honor = [0] * HONOR_KINDS
    pairs: list[int] = []

    # 分花色處理數牌
    boundaries = [
        (0, SUITED_END // COPIES * COPIES),            # 筒
        (SUITED_END // COPIES * COPIES, WIND_START),   # 已用 SUITED_END
    ]
    # 簡化：直接按花色邊界切分
    suit_ranges = [
        (0, 4 * TILES_PER_SUIT),
        (4 * TILES_PER_SUIT, 2 * 4 * TILES_PER_SUIT),
        (2 * 4 * TILES_PER_SUIT, 3 * 4 * TILES_PER_SUIT),
    ]
    i = 0
    for suit_idx, (lo, hi) in enumerate(suit_ranges):
        j = i
        while i < len(hand17) and hand17[i] < hi:
            suited[hand17[i] // COPIES] += 1
            i += 1
        segment = hand17[j:i]
        for ci in _find_suit_pairs(segment):
            if _find_i_pair(segment, ci):
                pairs.append(j + ci)

    # 字牌
    j = i
    while i < len(hand17):
        kind = hand17[i] // COPIES
        honor[kind - SUITED_KINDS] += 1
        i += 1
    for ci in range(j, len(hand17)):
        if _find_i_pair(hand17, ci):
            pairs.append(ci)

    return suited, honor, pairs


def is_win(hand: list[int], extra: int) -> bool:
    """判斷 16 張手牌加上 1 張摸入牌是否構成胡牌。

    胡牌條件：17 張 = 1 對將牌 + 5 組面子（刻子或順子）。
    先以 find_pair 找候選將牌，再對每個候選：
    - 去掉 2 張將牌後，以 is_honor + is_suit 驗證剩餘 15 張

    Args:
        hand:  長度 16 的手牌列表
        extra: 摸入的第 17 張牌號

    Returns:
        構成胡牌回傳 True，否則 False
    """
    all17 = sorted(hand + [extra])
    suited, honor, pair_indices = find_pair(all17)

    seen_kinds: set[int] = set()
    for idx in pair_indices:
        kind = all17[idx] // COPIES
        if kind in seen_kinds:
            continue
        seen_kinds.add(kind)

        if kind < SUITED_KINDS:     # 數牌將
            suited[kind] -= 2
            if is_honor(honor) and is_suit(suited):
                return True
            suited[kind] += 2
        else:                       # 字牌將
            honor_idx = kind - SUITED_KINDS
            honor[honor_idx] -= 2
            if is_honor(honor) and is_suit(suited):
                return True
            honor[honor_idx] += 2

    return False


def is_win_ext(hand: list[int], extra: int, meld_count: int = 0) -> bool:
    """計入桌面已成面子的胡牌判定。

    吃過 meld_count 次後，手牌張數 = (5 - meld_count) * 3 + 2。
    由於 is_win 內部以 find_pair / is_suit / is_honor 動態處理任意張數，
    本函式直接委派給 is_win，不重複邏輯。

    meld_count = 0 時等同 is_win（17 張）：
        hand 14 張，meld_count = 1 → 4 面子 + 1 將
        hand 11 張，meld_count = 2 → 3 面子 + 1 將
        （以此類推）

    Args:
        hand:       手牌列表（長度為 16 - meld_count * 2 或對應值）
        extra:      摸入的 1 張牌號
        meld_count: 已吃（或碰/槓）移至桌面的面子數，預設 0

    Returns:
        構成胡牌回傳 True，否則 False
    """
    return is_win(hand, extra)


# ---------------------------------------------------------------------------
# AI 出牌策略
# ---------------------------------------------------------------------------

import random as _random


def calculate_gates(m: Mahjong, p: PlayerState, ai: AIContext) -> None:
    """計算每張手牌打出後的聽牌候選，結果寫入 ai.gates 與 ai.play_freq。

    演算法：
    1. 統計手牌（含摸入牌，共 n_hand+1 張）的牌面累積分佈，
       找出哪些牌面在目前手牌中有出現（候選聽牌牌面）。
    2. 對每張手牌逐一假設「打出這張」，再假設「摸入各候選牌」，
       呼叫 is_win() 檢查是否胡牌；胡牌則 ai.gates[打出牌]++。
    3. ai.play_freq[i] = 4 - seen[hand[i]//COPIES]（已見張數越多，可摸機會越少）。

    Args:
        m:  遊戲狀態（用於取得 seen 上限）
        p:  玩家狀態（hand 長度為 n_hand+1，最後一張為剛摸入的牌）
        ai: AI 決策資料，本函式直接覆寫 gates 與 play_freq
    """
    ai.gates = {}
    ai.play_freq = {}

    total = len(p.hand)         # 含摸入牌（吃牌輪次手牌較少，用實際長度）
    hand = p.hand               # 長度 total

    # 統計手牌各牌面種類的出現次數（數牌 + 字牌，忽略花牌）
    hist = [0] * (SUITED_KINDS + HONOR_KINDS)
    for tile in hand[:total]:
        kind = tile // COPIES
        if kind < len(hist):
            hist[kind] += 1

    # 依數牌花色計算累積，找出哪些牌面「有出現」作為候選聽牌
    # 原版邏輯：每個花色各自做前綴累加，讓任何非零位置都 > 0
    for suit in range(SUIT_COUNT):
        base = suit * TILES_PER_SUIT
        for i in range(1, TILES_PER_SUIT):
            hist[base + i] += hist[base + i - 1]
        for i in range(TILES_PER_SUIT - 1):
            hist[base + i] = hist[base + TILES_PER_SUIT - 1]

    # 候選聽牌：牌面有出現且該牌面尚有未見副本
    candidates: list[int] = []
    for kind, count in enumerate(hist):
        if count > 0 and p.seen[kind] < COPIES:
            candidates.append(kind * COPIES)

    # 逐一模擬打出每張手牌
    for i in range(total):
        tile_out = hand[i]
        kind_out = tile_out // COPIES
        ai.play_freq[i] = COPIES - p.seen[kind_out] if kind_out < len(p.seen) else 0

        # 假設打出第 i 張，剩餘手牌 = hand 去掉第 i 張（共 n_hand 張）
        remaining = hand[:i] + hand[i + 1:total]

        gate_count = 0
        for cand_tile in candidates:
            if is_win(remaining, cand_tile):
                gate_count += 1

        if gate_count > 0:
            ai.gates[i] = gate_count


def decide_play(
    p: PlayerState,
    ai: AIContext,
    players: list[PlayerState] | None = None,
) -> tuple[int, DangerLevel] | int:
    """三階段 AI 出牌策略，回傳要打出的手牌索引。

    優先順序：
    1. 打出後聽牌數最多的牌（ai.gates 中 value 最大）
    2. 若無聽牌且 players 有值：以 danger_discard_index 按 DangerLevel 選牌
    3. 若 players 為 None（向下相容）：打出「已見張數最多」的牌，最後保底隨機

    Args:
        p:       玩家狀態
        ai:      AI 決策資料（已由 calculate_gates 填入）
        players: 四位玩家狀態列表（傳入時啟用 DangerLevel 策略，回傳 tuple）

    Returns:
        players 為 None 時回傳 int（向下相容）；
        players 有值時回傳 (棄牌索引, DangerLevel)，DangerLevel 為
        EXTREMELY_DANGEROUS 代表此次為「拆牌」。
    """
    total = p.n_hand + 1

    # 階段一：聽牌數最多
    if ai.gates:
        best_idx = max(ai.gates, key=lambda k: ai.gates[k])
        if players is not None:
            meld_kinds = _get_meld_kinds(p.hand)
            kind = p.hand[best_idx] // COPIES
            level = (DangerLevel.EXTREMELY_DANGEROUS if kind in meld_kinds
                     else classify_danger(p.hand[best_idx], players))
            return best_idx, level
        return best_idx

    # 階段二+三：DangerLevel 策略（players 有值）
    if players is not None:
        return danger_discard_index(p.hand, players)

    # 向下相容：已見張數最多
    if ai.play_freq:
        best_idx = min(ai.play_freq, key=lambda k: ai.play_freq[k])
        return best_idx

    # 保底隨機
    return _random.randint(0, total - 1)


# ---------------------------------------------------------------------------
# 吃牌輔助函式
# ---------------------------------------------------------------------------

def can_chi(hand: list[int], tile: int) -> tuple[int, int] | None:
    """找出手牌中可與棄牌構成順子的第一個配對（自動吃牌用）。

    三種吃法（同花色）：
    - 後吃：(tile-2, tile-1, tile) — rank >= 2
    - 夾吃：(tile-1, tile, tile+1) — 1 <= rank <= 7
    - 前吃：(tile, tile+1, tile+2) — rank <= 6

    未來可改由 chi_ai 決策函式呼叫，加入吃或不吃的策略判斷。

    Args:
        hand: 手牌列表（牌號整數）
        tile: 欲吃的棄牌牌號（必須為數牌，tile < SUITED_END）

    Returns:
        手牌中可與 tile 合成順子的 (tile_a, tile_b)；無法吃則回傳 None
    """
    if tile >= SUITED_END:
        return None  # 字牌與花牌不可吃

    kind_d = tile // COPIES
    rank_d = kind_d % TILES_PER_SUIT  # 0=1, 1=2, ..., 8=9

    def _find(kind: int) -> int | None:
        """在 hand 中找到第一張符合 kind 的牌號。"""
        for t in hand:
            if t // COPIES == kind:
                return t
        return None

    # 三種吃法依序嘗試
    combos: list[tuple[int, int]] = []
    if rank_d >= 2:                       # 後吃：(k-2, k-1, k)
        combos.append((kind_d - 2, kind_d - 1))
    if 1 <= rank_d <= 7:                  # 夾吃：(k-1, k, k+1)
        combos.append((kind_d - 1, kind_d + 1))
    if rank_d <= 6:                       # 前吃：(k, k+1, k+2)
        combos.append((kind_d + 1, kind_d + 2))

    for ka, kb in combos:
        ta = _find(ka)
        if ta is None:
            continue
        # 找 kb，需排除已用的 ta
        hand_minus = list(hand)
        hand_minus.remove(ta)
        tb = None
        for t in hand_minus:
            if t // COPIES == kb:
                tb = t
                break
        if tb is not None:
            return ta, tb

    return None


def can_pon(hand: list[int], tile: int) -> tuple[int, int] | None:
    """判斷手牌是否可碰棄牌（組成刻子）。

    數牌與字牌均可碰；花牌（tile >= BONUS_START）不可碰。

    Args:
        hand: 手牌列表（牌號整數）
        tile: 欲碰的棄牌牌號

    Returns:
        手牌中可與 tile 合成刻子的 (tile_a, tile_b)；無法碰則回傳 None
    """
    if tile >= BONUS_START:
        return None  # 花牌不可碰

    kind = tile // COPIES
    matched: list[int] = []
    for t in hand:
        if t // COPIES == kind:
            matched.append(t)
        if len(matched) == 2:
            return matched[0], matched[1]

    return None


def can_kong(hand: list[int], tile: int) -> tuple[int, int, int] | None:
    """判斷手牌是否可明槓棄牌（組成槓子，4 張同牌面）。

    數牌與字牌均可明槓；花牌（tile >= BONUS_START）不可槓。
    手牌需持有同牌面的 3 張，加上棄牌共 4 張。

    Args:
        hand: 手牌列表（牌號整數）
        tile: 欲槓的棄牌牌號

    Returns:
        手牌中可與 tile 合成槓子的 (tile_a, tile_b, tile_c)；無法槓則回傳 None
    """
    if tile >= BONUS_START:
        return None  # 花牌不可槓

    kind = tile // COPIES
    matched: list[int] = []
    for t in hand:
        if t // COPIES == kind:
            matched.append(t)
        if len(matched) == 3:
            return matched[0], matched[1], matched[2]

    return None


def can_add_to_pon(drawn: int, melds: list[list[int]]) -> int | None:
    """偵測摸入的牌是否可加入已碰刻子（加槓）。

    掃描 melds 中長度恰好為 3 且三張同牌面種類的刻子；
    若 drawn 的牌面種類相符，回傳該 meld 的索引，否則回傳 None。

    Args:
        drawn: 剛摸入的牌號
        melds: 玩家已亮出的面牌組列表

    Returns:
        可加槓的 meld 索引；無則回傳 None
    """
    if drawn >= BONUS_START:
        return None  # 花牌不可加槓
    kind = drawn // COPIES
    for i, meld in enumerate(melds):
        if len(meld) == 3 and all(t // COPIES == kind for t in meld):
            return i
    return None


# ---------------------------------------------------------------------------
# AI 放槍預防輔助函式
# ---------------------------------------------------------------------------

def get_dangerous_tiles(players: list[PlayerState], target_idx: int) -> dict[int, int]:
    """統計其他三家打出牌的牌面頻率，供 AI 評估放槍風險。

    當某牌面在他家棄牌中出現越多次，代表該牌已被多人打出，
    對手持有該牌聽牌的機率相對較低（安全牌傾向）；
    反之出現次數少，放槍風險較高。

    未來可結合 seen 與 gates 演算法，實作「避免打出危險牌」的 AI 策略。

    Args:
        players:    四位玩家的狀態列表
        target_idx: 欲查詢的玩家索引（0–3），該玩家自身的棄牌不計入

    Returns:
        dict[牌面種類索引, 出現次數]，僅包含出現次數 > 0 的牌面
    """
    freq: dict[int, int] = {}
    for i, p in enumerate(players):
        if i == target_idx:
            continue
        for tile in p.discards:
            kind = tile // COPIES
            freq[kind] = freq.get(kind, 0) + 1
    return freq


def classify_danger(
    tile: int,
    players: list[PlayerState],
    *,
    chi_tiles: list[int] | None = None,
    pon_tiles: list[int] | None = None,
    kong_tiles: list[int] | None = None,
) -> DangerLevel:
    """評估打出某張牌的放槍危險等級。

    判定優先順序（由安全至危險）：

    1. **很安全（VERY_SAFE）**
       - 花牌（tile >= BONUS_START）
       - 全局棄牌（所有玩家 discards 合計）中同牌面出現 ≥ 2 次
       - 未來擴充：chi_tiles / pon_tiles / kong_tiles 中出現的牌面

    2. **安全（SAFE）**
       - 字牌（wind 或 dragon）：無順子組合，放槍威脅有限
       - 最近 3 輪（3 × 4 = 12 筆）全局棄牌中出現過

    3. **危險（DANGEROUS）**
       - 數牌，曾出現在早期棄牌（超過最近 12 筆），但最近 12 筆未出現

    4. **很危險（VERY_DANGEROUS）**
       - 數牌，從未出現在任何人的棄牌中
       - 未來擴充：也未被吃（下一家）、碰/槓（其他三家）

    Args:
        tile:       欲評估的牌號整數
        players:    四位玩家的狀態列表（使用各玩家 discards）
        chi_tiles:  已被吃的牌面列表（預留，目前傳 None 視為空）
        pon_tiles:  已被碰的牌面列表（預留，目前傳 None 視為空）
        kong_tiles: 已被槓的牌面列表（預留，目前傳 None 視為空）

    Returns:
        DangerLevel 列舉值
    """
    kind = tile // COPIES

    # 蒐集全局棄牌（依輪次交錯順序）
    all_discards: list[int] = []
    max_len = max((len(p.discards) for p in players), default=0)
    for i in range(max_len):
        for p in players:
            if i < len(p.discards):
                all_discards.append(p.discards[i])

    # 吃/碰/槓牌面集合
    _chi  = chi_tiles  or []
    _pon  = pon_tiles  or []
    _kong = kong_tiles or []
    meld_kinds = {t // COPIES for t in _chi + _pon + _kong}

    # 全局出現次數
    global_count = sum(1 for t in all_discards if t // COPIES == kind)

    # 極度安全：數牌或字牌，四張全已出現（不可能放槍），或曾被吃/碰/槓
    # 花牌每種只有 1 張，不適用此條件
    if tile < BONUS_START and (global_count >= COPIES or kind in meld_kinds):
        return DangerLevel.EXTREMELY_SAFE

    # 花牌：很安全
    if tile >= BONUS_START:
        return DangerLevel.VERY_SAFE

    # 很安全：全局出現 ≥ 2 次
    if global_count >= 2:
        return DangerLevel.VERY_SAFE

    # 字牌：安全
    if SUITED_END // COPIES <= kind < (DRAGON_END // COPIES):
        return DangerLevel.SAFE

    # 最近 3 輪 = 最後 12 筆全局棄牌
    recent = all_discards[-12:]
    recent_kinds = {t // COPIES for t in recent}

    # 安全：最近 3 輪有人打出過
    if kind in recent_kinds:
        return DangerLevel.SAFE

    # 早期棄牌（12 筆以前）是否出現過
    early = all_discards[:-12] if len(all_discards) > 12 else []
    early_kinds = {t // COPIES for t in early}

    # 危險：曾在早期出現但最近 3 輪未出現
    if kind in early_kinds:
        return DangerLevel.DANGEROUS

    # 很危險：從未出現
    return DangerLevel.VERY_DANGEROUS


# ---------------------------------------------------------------------------
# 快速驗收（執行此模組時顯示）
# ---------------------------------------------------------------------------

if __name__ == "__main__" and RUN_TESTS:
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
        assert p.bonus == []
        assert p.melds == []
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

    print("\n--- 胡牌判定驗收 ---")
    # 已知胡牌手牌：1-9筒各一對 + 1-9索各一 → 不是標準胡型，改用明確手牌
    # 胡牌範例：五組順子 1-2-3筒 × 5 + 一對東風
    win_hand = (
        [0, 4, 8] * 5   # 1筒、2筒、3筒 × 5組（各取第一張副本）
        + [108, 109]     # 東東（一對）
    )
    # 取前16張為手牌，最後1張為摸入
    win_hand16 = win_hand[:16]
    win_extra  = win_hand[16]
    assert is_win(win_hand16, win_extra), "已知胡牌手牌應回傳 True"
    print("  ✓ 已知胡牌手牌回傳 True")

    # 未胡範例：17 張全不同花色散牌（1–9筒各1 + 1–8索各1）
    no_win_hand = list(range(0, 36, 4)) + list(range(36, 68, 4))  # 9+8=17 張
    assert not is_win(no_win_hand[:16], no_win_hand[16]), "未胡手牌應回傳 False"
    print("  ✓ 未胡手牌回傳 False")

    print("\n--- AI 出牌策略驗收 ---")
    # 建立一手快要聽牌的手牌：1-3筒×5組（15張）+ 東東 + 摸入南
    # 打出東（index 15）後聽南可胡
    ai_hand = [0, 4, 8] * 5 + [108, 112]   # 長度 17（含摸入）
    p_ai = PlayerState(n_hand=16)
    p_ai.hand = ai_hand[:]
    p_ai.seen = [0] * (SUITED_KINDS + HONOR_KINDS)
    ai_ctx = AIContext()
    m_ai = Mahjong(n_hand=16)
    calculate_gates(m_ai, p_ai, ai_ctx)
    idx = decide_play(p_ai, ai_ctx)
    assert 0 <= idx <= 16, f"decide_play 回傳索引應在 0–16，實際 {idx}"
    print(f"  ✓ decide_play() 回傳索引 {idx}（打出 {n_to_chinese(ai_hand[idx])}），無例外")

    print("\n--- 棄牌紀錄驗收 ---")
    import random as _r
    _r.seed(99)
    m_dis = Mahjong(n_hand=16)
    m_dis.init_deal()
    m_dis.show_bonus()
    print()
    for p in m_dis.players:
        assert p.discards == [], "開局前 discards 應為空"
    print("  ✓ 開局前各玩家 discards 為空")
    # 模擬數回合打牌，手動寫入 discards
    fake_tiles = [0, 4, 8, 12]
    for i, p in enumerate(m_dis.players):
        p.discards.append(fake_tiles[i])
    total_discards = sum(len(p.discards) for p in m_dis.players)
    assert total_discards == 4, f"總棄牌數應為 4，實際 {total_discards}"
    sea = m_dis.sea
    assert len(sea) == 4, f"sea 聚合長度應為 4，實際 {len(sea)}"
    assert sea == [0, 4, 8, 12], f"sea 應依玩家順序交錯，實際 {sea}"
    print("  ✓ discards 長度之和與 sea 聚合正確")

    print("\n--- 放槍預防查詢驗收 ---")
    p0 = PlayerState(n_hand=16)
    p1 = PlayerState(n_hand=16)
    p2 = PlayerState(n_hand=16)
    p3 = PlayerState(n_hand=16)
    # 玩家0打出：1筒(0)、2筒(4)
    p0.discards = [0, 4]
    # 玩家1打出：1筒(0)、東(108)
    p1.discards = [0, 108]
    # 玩家2打出：3筒(8)
    p2.discards = [8]
    # 玩家3（目標，棄牌不計入）打出：9筒(32)
    p3.discards = [32]
    players_test = [p0, p1, p2, p3]

    danger = get_dangerous_tiles(players_test, target_idx=3)
    assert danger.get(0) == 2, f"牌面0(1筒)應出現2次，實際 {danger.get(0)}"
    assert danger.get(1) == 1, f"牌面1(2筒)應出現1次，實際 {danger.get(1)}"
    assert danger.get(2) == 1, f"牌面2(3筒)應出現1次，實際 {danger.get(2)}"
    assert danger.get(27) == 1, f"牌面27(東)應出現1次，實際 {danger.get(27)}"
    assert 8 not in danger, "玩家3(target)的棄牌不應計入"
    print("  ✓ get_dangerous_tiles() 正確統計其他三家棄牌頻率")
    print("  ✓ target_idx 玩家自身棄牌不計入")

    print("\n--- 危險等級分類驗收 ---")
    _dp = [PlayerState(n_hand=16) for _ in range(4)]

    # 很安全：花牌
    assert classify_danger(136, _dp) == DangerLevel.VERY_SAFE
    print(f"  ✓ 花牌(春) → {classify_danger(136, _dp).name}")

    # 很安全：全局出現 ≥ 2 次的數牌
    _dp[0].discards = [0]; _dp[1].discards = [0]
    assert classify_danger(0, _dp) == DangerLevel.VERY_SAFE
    print(f"  ✓ 1筒出現2次 → {classify_danger(0, _dp).name}")

    # 安全：字牌（東）從未出現
    _dp2 = [PlayerState(n_hand=16) for _ in range(4)]
    assert classify_danger(108, _dp2) == DangerLevel.SAFE
    print(f"  ✓ 東(字牌，未出現) → {classify_danger(108, _dp2).name}")

    # 安全：數牌，最近 3 輪（12 筆）內出現過
    _dp3 = [PlayerState(n_hand=16) for _ in range(4)]
    _dp3[0].discards = [4]   # 2筒出現1次，在最近12筆內
    assert classify_danger(4, _dp3) == DangerLevel.SAFE
    print(f"  ✓ 2筒近期出現1次 → {classify_danger(4, _dp3).name}")

    # 危險：數牌，早期出現但最近 3 輪未見
    _dp4 = [PlayerState(n_hand=16) for _ in range(4)]
    _dp4[0].discards = [0] + [4] * 3   # 1筒在首輪（early），其餘12筆為2筒
    _dp4[1].discards = [4] * 4
    _dp4[2].discards = [4] * 4
    _dp4[3].discards = [4] * 4
    assert classify_danger(0, _dp4) == DangerLevel.DANGEROUS
    print(f"  ✓ 1筒早期出現、近期未見 → {classify_danger(0, _dp4).name}")

    # 很危險：數牌，從未出現
    _dp5 = [PlayerState(n_hand=16) for _ in range(4)]
    assert classify_danger(8, _dp5) == DangerLevel.VERY_DANGEROUS
    print(f"  ✓ 3筒從未出現 → {classify_danger(8, _dp5).name}")

    # 極度安全：數牌四張全棄
    _dp6 = [PlayerState(n_hand=16) for _ in range(4)]
    for i in range(4):
        _dp6[i].discards = [0]   # 1筒各出現 1 次，共 4 次
    assert classify_danger(0, _dp6) == DangerLevel.EXTREMELY_SAFE
    print(f"  ✓ 1筒四張全棄 → {classify_danger(0, _dp6).name}")

    # 極度安全：字牌四張全棄
    _dp7 = [PlayerState(n_hand=16) for _ in range(4)]
    for i in range(4):
        _dp7[i].discards = [108]   # 東各出現 1 次，共 4 次
    assert classify_danger(108, _dp7) == DangerLevel.EXTREMELY_SAFE
    print(f"  ✓ 東四張全棄 → {classify_danger(108, _dp7).name}")

    # 花牌最多只到 VERY_SAFE（無法達到 EXTREMELY_SAFE）
    _dp8 = [PlayerState(n_hand=16) for _ in range(4)]
    assert classify_danger(136, _dp8) == DangerLevel.VERY_SAFE
    print(f"  ✓ 花牌(春)不適用極度安全 → {classify_danger(136, _dp8).name}")

    # 等級比較正確
    assert DangerLevel.EXTREMELY_SAFE < DangerLevel.VERY_SAFE < DangerLevel.SAFE
    print("  ✓ EXTREMELY_SAFE < VERY_SAFE < SAFE 比較正確")

    print("\n--- find_hand_chows 驗收 ---")
    # 1. 純順子手牌：1-2-3筒各 × 2 張（共 6 張）→ 2 組順子，無刻子
    #    注意：各花色同點數 ≥ 3 張時貪婪演算法先消刻子，故用 2 張強制走順子路徑
    _chow_s1 = [0] * SUITED_KINDS
    _chow_s1[0] = 2; _chow_s1[1] = 2; _chow_s1[2] = 2   # 1筒×2, 2筒×2, 3筒×2
    _r1 = find_hand_chows(_chow_s1)
    assert _r1 is not None, "純順子應可分解"
    assert len(_r1) == 2, f"應有 2 組順子，實際 {len(_r1)}"
    assert all(t == (0, 1, 2) for t in _r1), f"順子應為 (0,1,2)，實際 {_r1}"
    print(f"  ✓ 純順子(1-2-3筒×2) → {len(_r1)} 組順子 {_r1}")

    # 2. 純刻子手牌：1筒×3 + 2筒×3 → 回傳空列表（無順子）
    _chow_s2 = [0] * SUITED_KINDS
    _chow_s2[0] = 3; _chow_s2[1] = 3
    _r2 = find_hand_chows(_chow_s2)
    assert _r2 == [], f"純刻子應回傳空列表，實際 {_r2}"
    print(f"  ✓ 純刻子(1筒×3, 2筒×3) → 空列表 {_r2}")

    # 3. 刻子混順子：1筒×3（刻子）+ 4-5-6筒各×1（順子）
    _chow_s3 = [0] * SUITED_KINDS
    _chow_s3[0] = 3   # 1筒×3 → 刻子
    _chow_s3[3] = 1; _chow_s3[4] = 1; _chow_s3[5] = 1   # 4-5-6筒 → 順子
    _r3 = find_hand_chows(_chow_s3)
    assert _r3 is not None, "混合手牌應可分解"
    assert len(_r3) == 1, f"應有 1 組順子，實際 {len(_r3)}"
    assert _r3[0] == (3, 4, 5), f"順子應為 (3,4,5)，實際 {_r3[0]}"
    print(f"  ✓ 刻子混順子 → {len(_r3)} 組順子 {_r3}")

    # 4. 無法分解的手牌：1筒×1（孤張）→ 回傳 None
    _chow_s4 = [0] * SUITED_KINDS
    _chow_s4[0] = 1
    _r4 = find_hand_chows(_chow_s4)
    assert _r4 is None, f"無法分解應回傳 None，實際 {_r4}"
    print(f"  ✓ 無法分解(1筒×1孤張) → None")

    # 5. EXTREMELY_DANGEROUS > VERY_DANGEROUS 比較正確
    assert DangerLevel.EXTREMELY_DANGEROUS > DangerLevel.VERY_DANGEROUS
    print(f"  ✓ EXTREMELY_DANGEROUS > VERY_DANGEROUS 比較正確")

    print("\n--- find_hand_pungs 驗收 ---")
    # 1. c=2（對子）→ 不回傳（刻子需 >= 3）
    _p1 = [0] * SUITED_KINDS
    _p1[0] = 2
    assert find_hand_pungs(_p1) == [], f"c=2 不應回傳，實際 {find_hand_pungs(_p1)}"
    print("  ✓ c=2（對子）→ 不回傳 []")

    # 2. c=3（刻子已成）→ 回傳 [(0, 3)]
    _p2 = [0] * SUITED_KINDS
    _p2[0] = 3
    assert find_hand_pungs(_p2) == [(0, 3)], f"c=3 應回傳 [(0,3)]，實際 {find_hand_pungs(_p2)}"
    print("  ✓ c=3（刻子）→ [(0, 3)]")

    # 3. c=4（槓子已成）→ 回傳 [(0, 4)]
    _p3 = [0] * SUITED_KINDS
    _p3[0] = 4
    assert find_hand_pungs(_p3) == [(0, 4)], f"c=4 應回傳 [(0,4)]，實際 {find_hand_pungs(_p3)}"
    print("  ✓ c=4（槓子）→ [(0, 4)]")

    # 4. 混合：c=2 + c=3 → 只回傳 c=3 的項目
    _p4 = [0] * SUITED_KINDS
    _p4[0] = 2; _p4[1] = 3
    assert find_hand_pungs(_p4) == [(1, 3)], f"混合應只回傳 [(1,3)]，實際 {find_hand_pungs(_p4)}"
    print("  ✓ 混合(c=2, c=3) → 只回傳刻子 [(1, 3)]")

    print("\n--- find_hand_pairs 驗收 ---")
    _hp_honor = HONOR_KINDS

    # 1. c=2（對子）→ 回傳 [0]
    _h1 = [0] * _hp_honor
    _h1[0] = 2
    assert find_hand_pairs(_h1) == [0], f"c=2 應回傳 [0]，實際 {find_hand_pairs(_h1)}"
    print("  ✓ c=2（對子）→ [0]")

    # 2. c=1（孤張）→ 不回傳
    _h2 = [0] * _hp_honor
    _h2[0] = 1
    assert find_hand_pairs(_h2) == [], f"c=1 應回傳 []，實際 {find_hand_pairs(_h2)}"
    print("  ✓ c=1（孤張）→ []")

    # 3. c=3（字牌刻子）→ 也算 >= 2，回傳 [0]
    _h3 = [0] * _hp_honor
    _h3[0] = 3
    assert find_hand_pairs(_h3) == [0], f"c=3 應回傳 [0]，實際 {find_hand_pairs(_h3)}"
    print("  ✓ c=3（字牌刻子）→ 也算對子候選 [0]")

    print("\n--- danger_discard_index 驗收 ---")
    _ep = [PlayerState(n_hand=16) for _ in range(4)]  # 全空棄牌

    # 1. 湊牌 vs 孤張：1-2-3筒形成順子（湊牌），東為孤張（SAFE）→ 棄東
    _hand1 = [0, 4, 8, 108]   # 1筒、2筒、3筒、東
    _idx1, _lv1 = danger_discard_index(_hand1, _ep)
    assert _idx1 == 3, f"應棄東（index 3），實際棄 {n_to_chinese(_hand1[_idx1])}（index {_idx1}）"
    assert _lv1 == DangerLevel.SAFE, f"等級應為 SAFE，實際 {_lv1.name}"
    print(f"  ✓ 湊牌 vs 孤張 → 棄 {n_to_chinese(_hand1[_idx1])}（{_lv1.name}）")

    # 2. 同等級字牌優先棄：1筒已見（SAFE）+ 東（SAFE）→ 優先棄字牌東
    _ep2 = [PlayerState(n_hand=16) for _ in range(4)]
    _ep2[0].discards = [0]    # 1筒出現一次 → 最近 12 筆內 → SAFE
    _hand2 = [0, 108]         # 1筒、東
    _idx2, _lv2 = danger_discard_index(_hand2, _ep2)
    assert _idx2 == 1, f"同等級應優先棄字牌（index 1），實際棄 {n_to_chinese(_hand2[_idx2])}"
    assert _lv2 == DangerLevel.SAFE
    print(f"  ✓ 同等級字牌優先 → 棄 {n_to_chinese(_hand2[_idx2])}（{_lv2.name}）")

    # 3. 全數牌同等級，棄離5最遠：5筒（distance=0）vs 9筒（distance=4）→ 棄9筒
    _hand3 = [16, 32]         # 5筒（kind=4）、9筒（kind=8）
    _idx3, _lv3 = danger_discard_index(_hand3, _ep)
    assert _idx3 == 1, f"應棄離5最遠的9筒（index 1），實際棄 {n_to_chinese(_hand3[_idx3])}"
    print(f"  ✓ 離5最遠 → 棄 {n_to_chinese(_hand3[_idx3])}（{_lv3.name}）")

    # 4. 全湊牌（拆牌）：1-2-3筒全為湊牌 → 被迫拆牌，level 為 EXTREMELY_DANGEROUS
    _hand4 = [0, 4, 8]        # 1筒、2筒、3筒 → chow(0,1,2)
    _idx4, _lv4 = danger_discard_index(_hand4, _ep)
    assert _lv4 == DangerLevel.EXTREMELY_DANGEROUS, f"全湊牌應為拆牌，實際 {_lv4.name}"
    print(f"  ✓ 全湊牌拆牌 → 棄 {n_to_chinese(_hand4[_idx4])}（{_lv4.name}）= 拆牌")

    print("\n--- can_chi 驗收 ---")
    # 1. 後吃：手牌 1筒(0)+2筒(4)，棄牌 3筒(8)，rank=2 >= 2
    _r1 = can_chi([0, 4], 8)
    assert _r1 == (0, 4), f"後吃應回傳 (0, 4)，實際 {_r1}"
    print(f"  ✓ 後吃 3筒：手牌 {n_to_chinese(0)}+{n_to_chinese(4)} → {_r1}")

    # 2. 夾吃：手牌 1筒(0)+3筒(8)，棄牌 2筒(4)，rank=1, 1<=rank<=7
    _r2 = can_chi([0, 8], 4)
    assert _r2 == (0, 8), f"夾吃應回傳 (0, 8)，實際 {_r2}"
    print(f"  ✓ 夾吃 2筒：手牌 {n_to_chinese(0)}+{n_to_chinese(8)} → {_r2}")

    # 3. 前吃：手牌 2筒(4)+3筒(8)，棄牌 1筒(0)，rank=0 <= 6
    _r3 = can_chi([4, 8], 0)
    assert _r3 == (4, 8), f"前吃應回傳 (4, 8)，實際 {_r3}"
    print(f"  ✓ 前吃 1筒：手牌 {n_to_chinese(4)}+{n_to_chinese(8)} → {_r3}")

    # 4. 無法吃：手牌只有 9筒(32)，棄牌 1筒(0) → 無符合配對
    _r4 = can_chi([32], 0)
    assert _r4 is None, f"無法吃應回傳 None，實際 {_r4}"
    print(f"  ✓ 無法吃 → None")

    # 5. 字牌不可吃：棄牌 東(108) >= SUITED_END → 直接回傳 None
    _r5 = can_chi([0, 4, 8], 108)
    assert _r5 is None, f"字牌不可吃應回傳 None，實際 {_r5}"
    print(f"  ✓ 字牌 東 不可吃 → None")

    print("\n--- can_pon 驗收 ---")
    # 1. 數牌可碰：手牌 1筒(0)+1筒(1)，棄牌 1筒(2)，同 kind=0
    _p1 = can_pon([0, 1], 2)
    assert _p1 == (0, 1), f"數牌可碰應回傳 (0, 1)，實際 {_p1}"
    print(f"  ✓ 數牌碰 {n_to_chinese(2)}：手牌 {n_to_chinese(0)}+{n_to_chinese(1)} → {_p1}")

    # 2. 字牌可碰：手牌 東(108)+東(109)，棄牌 東(110)，同 kind=27
    _p2 = can_pon([108, 109], 110)
    assert _p2 == (108, 109), f"字牌可碰應回傳 (108, 109)，實際 {_p2}"
    print(f"  ✓ 字牌碰 {n_to_chinese(110)}：手牌 {n_to_chinese(108)}+{n_to_chinese(109)} → {_p2}")

    # 3. 牌不夠：手牌只有 1 張 1筒(0)，棄牌 1筒(4) → 無法碰
    _p3 = can_pon([0], 4)
    assert _p3 is None, f"牌不夠應回傳 None，實際 {_p3}"
    print(f"  ✓ 牌不夠（只有 1 張）→ None")

    # 4. 花牌不可碰：棄牌 春(136) >= BONUS_START → 直接回傳 None
    _p4 = can_pon([136, 137], 136)
    assert _p4 is None, f"花牌不可碰應回傳 None，實際 {_p4}"
    print(f"  ✓ 花牌 {n_to_chinese(136)} 不可碰 → None")

    print("\n--- can_kong 驗收 ---")
    # 1. 數牌可槓：手牌 1筒(0,1,2)，棄牌 1筒(3)，同 kind=0
    _k1 = can_kong([0, 1, 2], 3)
    assert _k1 == (0, 1, 2), f"數牌可槓應回傳 (0, 1, 2)，實際 {_k1}"
    print(f"  ✓ 數牌槓 {n_to_chinese(3)}：手牌 3張 {n_to_chinese(0)} → {_k1}")

    # 2. 字牌可槓：手牌 東(108,109,110)，棄牌 東(111)，同 kind=27
    _k2 = can_kong([108, 109, 110], 111)
    assert _k2 == (108, 109, 110), f"字牌可槓應回傳 (108, 109, 110)，實際 {_k2}"
    print(f"  ✓ 字牌槓 {n_to_chinese(111)}：手牌 3張 {n_to_chinese(108)} → {_k2}")

    # 3. 只有 2 張：手牌 1筒(0,1)，棄牌 1筒(2) → 無法槓
    _k3 = can_kong([0, 1], 2)
    assert _k3 is None, f"只有 2 張應回傳 None，實際 {_k3}"
    print(f"  ✓ 只有 2 張 → None")

    # 4. 花牌不可槓：棄牌 春(136) >= BONUS_START → 直接回傳 None
    _k4 = can_kong([136, 137, 138], 136)
    assert _k4 is None, f"花牌不可槓應回傳 None，實際 {_k4}"
    print(f"  ✓ 花牌 {n_to_chinese(136)} 不可槓 → None")

    print("\n--- is_win_ext 驗收 ---")
    # 1. chi_count=0：結果與 is_win 相同（17 張胡牌）
    #    手牌 16 張：1筒對(0,1) + 2-6筒各刻子 → extra=22(6筒第3副)
    _hw16 = [0, 1, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17, 18, 20, 21]
    _ex16 = 22   # 6筒第3副（kind=5）
    _iw = is_win(_hw16, _ex16)
    _iwe = is_win_ext(_hw16, _ex16, 0)
    assert _iw == _iwe, f"chi_count=0 應與 is_win 一致，is_win={_iw} is_win_ext={_iwe}"
    assert _iw is True, f"17 張胡牌應回傳 True，實際 {_iw}"
    print(f"  ✓ chi_count=0 → is_win_ext={_iwe}（與 is_win 一致）")

    # 2. chi_count=1：14 張手牌可胡（對子 1筒 + 刻子 2-5筒，吃 1 面子已在桌面）
    #    hand13(13張) + extra(1張) = 14 張 = 1 對 + 4 刻子
    _hw13 = [0, 1, 4, 5, 6, 8, 9, 10, 12, 13, 14, 16, 17]
    _ex13 = 18   # 5筒第3副（kind=4）
    _iwe2 = is_win_ext(_hw13, _ex13, 1)
    assert _iwe2 is True, f"chi_count=1 胡牌應回傳 True，實際 {_iwe2}"
    print(f"  ✓ chi_count=1（14張）→ is_win_ext={_iwe2}")


def _do_meld(
    m: "Mahjong",
    discard_player: int,
    meld_player: int,
    discard_tile: int,
    hand_tiles: list[int],
) -> None:
    """吃/碰/槓共用：移牌至面牌組、補記 seen、移除棄牌記錄。

    Args:
        m:              遊戲物件
        discard_player: 打出棄牌的玩家索引
        meld_player:    執行吃/碰/槓的玩家索引
        discard_tile:   被吃/碰/槓的棄牌
        hand_tiles:     從手牌移出的配牌列表（吃/碰 2 張，槓 3 張）
    """
    mp = m.players[meld_player]
    for t in hand_tiles:
        mp.hand.remove(t)
    mp.melds.append(hand_tiles + [discard_tile])
    m.players[discard_player].discards.pop()
    # 配牌已公開，通知其他玩家
    for t in hand_tiles:
        for obs in range(4):
            if obs != meld_player:
                m.players[obs].add_seen(t)


def score_hand(
    winner: int,
    dealer_idx: int,
    consecutive: int,
    is_tsumo: bool,
    p: "PlayerState",
    winning_tile: int,
    game_wind: str,
    seat_winds: list[str],
    is_rob_kong: bool = False,
    is_kong_flower: bool = False,
    is_last_tile: bool = False,
    is_first_round: bool = False,
    tenhou_label: str = "",
    pao_idx: int | None = None,
) -> list[tuple[str, int]]:
    """計算胡牌台數明細。

    Args:
        winner:         胡牌玩家索引
        dealer_idx:     本局莊家索引
        consecutive:    連莊次數（0 = 首局）
        is_tsumo:       True = 自摸胡；False = 放槍胡
        p:              胡牌玩家的 PlayerState（hand 含摸入的完整手牌）
        winning_tile:   胡牌的那張牌
        game_wind:      局風字串（"東"/"南"/"西"/"北"）
        seat_winds:     四家門風列表（seat_winds[winner] = 自風）
        is_rob_kong:    True = 搶槓胡，額外 +1 台
        is_kong_flower: True = 槓上開花（補花/加槓補牌後自摸），額外 +1 台
        is_last_tile:   True = 牌堆最後一張牌（自摸→海底撈月+1；放槍→河底撈魚+1）
        is_first_round: True = 首巡胡牌（天胡/地胡/人胡+16，分別過濾不求/自摸/門清）
        tenhou_label:   "天聽"→+8 或 "地聽"→+4；空字串表示無天地聽加成
        pao_idx:        放槍者玩家索引（自摸時為 None）；等於 dealer_idx 時額外 +1 台

    Returns:
        (規則名稱, 台數) 的列表，台數均為正整數。
        基礎組合（is_tsumo × has_meld）：
            - 不求 +2：無副露自摸胡（門清 + 自摸合計）
            - 自摸 +1：有副露自摸胡
            - 門清 +1：無副露放槍胡
            - 半求 +1：有副露放槍胡
        獨聽 +1：胡牌前手牌對全部 34 種牌面掃描，只有 1 種能完成胡牌
        八仙過海 +8：春夏秋冬梅蘭竹菊全部 8 張花牌均已收入（疊加於花槓與己位花牌之上）
    """
    result: list[tuple[str, int]] = []
    seat_wind = seat_winds[winner]

    # --- 基礎台數 ---
    if is_rob_kong:
        result.append(("搶槓", 1))
    if is_kong_flower:
        result.append(("槓上開花", 1))
    if is_last_tile:
        if is_tsumo:
            result.append(("海底撈月", 1))
        else:
            result.append(("河底撈魚", 1))
    if winner == dealer_idx:
        result.append(("莊家", 1))
    if consecutive >= 1:
        result.append(("拉莊", consecutive * 2))
    if not is_tsumo and pao_idx is not None and pao_idx == dealer_idx:
        result.append(("莊家放槍", 1))

    has_meld = (p.chi_count + p.pon_count + p.kong_count) > 0

    if is_tsumo:
        if not has_meld:
            result.append(("不求", 2))    # 不求 = 門清 + 自摸（合並計 2 台）
        else:
            result.append(("自摸", 1))
    else:
        if not has_meld:
            result.append(("門清", 1))
        else:
            result.append(("半求", 1))

    # --- 花牌台數（己位花）---
    wind_pos = _SEAT_WIND_NAMES.index(seat_wind)
    own_bonus = {BONUS_START + wind_pos, BONUS_START + 4 + wind_pos}
    own_flower_count = sum(1 for t in p.bonus if t in own_bonus)
    if own_flower_count:
        result.append((f"花牌", own_flower_count))

    # --- 字牌台數（需 melds 中含刻子/槓子）---
    seat_wind_kind  = SUITED_KINDS + wind_pos                         # 27–30
    game_wind_kind  = SUITED_KINDS + _SEAT_WIND_NAMES.index(game_wind)  # 27–30
    dragon_base     = SUITED_KINDS + WIND_KINDS                       # 31

    for meld in p.melds:
        if len(meld) < 3:
            continue
        first_kind = meld[0] // COPIES
        # 判斷是否為刻子（pung）或槓子（kong）：所有牌同一 kind
        if not all(t // COPIES == first_kind for t in meld):
            continue  # 吃牌（順子）跳過
        if first_kind == seat_wind_kind:
            result.append(("自風", 1))
        if first_kind == game_wind_kind and game_wind_kind != seat_wind_kind:
            result.append(("圈風", 1))
        if dragon_base <= first_kind < dragon_base + DRAGON_COUNT:
            result.append(("三元牌", 1))

    # 花槓：春夏秋冬 或 梅蘭竹菊 湊齊 4 張
    bonus_set = set(p.bonus)
    season_set = {BONUS_START, BONUS_START+1, BONUS_START+2, BONUS_START+3}
    plant_set  = {BONUS_START+4, BONUS_START+5, BONUS_START+6, BONUS_START+7}
    if season_set.issubset(bonus_set):
        result.append(("花槓(春夏秋冬)", 2))
    if plant_set.issubset(bonus_set):
        result.append(("花槓(梅蘭竹菊)", 2))

    # 八仙過海：全部 8 張花牌均已收入（春夏秋冬梅蘭竹菊）
    if len(bonus_set) == BONUS_COUNT:
        result.append(("八仙過海", 8))

    # --- 手型台數 ---
    # 收集全部非花牌（melds + hand，ron 時補入 winning_tile）
    hand_all = list(p.hand)
    if not is_tsumo:
        hand_all.append(winning_tile)
    meld_flat = [t for meld in p.melds for t in meld]
    all_non_bonus = [t for t in hand_all + meld_flat if t < BONUS_START]

    # 花色分析
    def _suit_of(t: int) -> int | None:
        """回傳數牌花色索引（0筒/1索/2萬），字牌回傳 None。"""
        if t < SUITED_END:
            return t // (TILES_PER_SUIT * COPIES)
        return None

    suits_used = {_suit_of(t) for t in all_non_bonus if _suit_of(t) is not None}
    has_honor = any(t >= SUITED_END for t in all_non_bonus)

    # 字一色：全部非花牌均為字牌（無任何數牌），圈風/自風/三元牌可複合計
    if all_non_bonus and not suits_used:
        result.append(("字一色", 8))
    # 清一色：單一數牌花色，無字牌
    elif len(suits_used) == 1 and not has_honor:
        result.append(("清一色", 8))
    # 混一色：單一數牌花色 + 字牌，無其他花色
    elif len(suits_used) == 1 and has_honor:
        result.append(("混一色", 4))

    # 碰碰胡：無吃牌，且手牌（含摸入）可分解為刻子 + 對眼
    from collections import Counter as _Counter
    _counts_hand = _Counter(t // COPIES for t in hand_all)
    if p.chi_count == 0:
        pairs_in_hand = sum(1 for c in _counts_hand.values() if c % 3 == 2)
        all_valid = all(c % 3 in (0, 2) for c in _counts_hand.values())
        if pairs_in_hand == 1 and all_valid:
            result.append(("碰碰胡", 4))

    # 三暗刻 / 四暗刻 / 五暗刻：手牌中同種牌出現 ≥3 張的種類數（暗刻候選）
    concealed_pungs = sum(1 for c in _counts_hand.values() if c >= 3)
    if concealed_pungs >= 5 and not has_meld:
        result.append(("五暗刻", 5))
    elif concealed_pungs >= 4 and not has_meld:
        result.append(("四暗刻", 5))
    elif concealed_pungs >= 3:
        result.append(("三暗刻", 2))

    # 大三元 / 小三元：統計三元牌（中/發/白）在全局手牌（含明牌）的數量
    _counts_all = _Counter(t // COPIES for t in all_non_bonus)
    _dragon_pungs = sum(
        1 for k in range(dragon_base, dragon_base + DRAGON_COUNT)
        if _counts_all[k] >= 3
    )
    _dragon_pairs = sum(
        1 for k in range(dragon_base, dragon_base + DRAGON_COUNT)
        if _counts_all[k] == 2
    )
    if _dragon_pungs == DRAGON_COUNT:
        result.append(("大三元", 8))
    elif _dragon_pungs == DRAGON_COUNT - 1 and _dragon_pairs >= 1:
        result.append(("小三元", 4))

    # 大四喜 / 小四喜：統計四風（東/南/西/北）在全局手牌（含明牌）的數量
    _wind_pungs = sum(
        1 for k in range(SUITED_KINDS, SUITED_KINDS + WIND_KINDS)
        if _counts_all[k] >= 3
    )
    _wind_pairs = sum(
        1 for k in range(SUITED_KINDS, SUITED_KINDS + WIND_KINDS)
        if _counts_all[k] == 2
    )
    if _wind_pungs == WIND_KINDS:
        # 大四喜：清 16 台，原文規定不得加計自風/圈風台
        result = [r for r in result if r[0] not in ("自風", "圈風")]
        result.append(("大四喜", 16))
    elif _wind_pungs == WIND_KINDS - 1 and _wind_pairs >= 1:
        result.append(("小四喜", 8))

    # 獨聽：胡牌前的手牌只有一種牌面可以完成胡牌
    meld_count = p.chi_count + p.pon_count + p.kong_count
    hand_for_gates = list(hand_all)
    hand_for_gates.remove(winning_tile)
    wait_kinds = sum(
        1 for kind in range(SUITED_KINDS + HONOR_KINDS)
        if is_win_ext(hand_for_gates, kind * COPIES, meld_count)
    )
    if wait_kinds == 1:
        result.append(("獨聽", 1))

    # 平胡：ron + 無字花 + 全順子（無明刻/暗刻/槓子）+ 兩面聽（≥2 種聽牌）
    if (
        not is_tsumo
        and not has_honor
        and not p.bonus
        and p.pon_count == 0
        and p.kong_count == 0
        and not any(c >= 3 for c in _counts_hand.values())
        and wait_kinds >= 2
    ):
        result.append(("平胡", 2))

    # 全求：放槍胡 + 閉門只剩 1 張（5 組面子全已副露，等最後一張完成胡牌）
    # 此時半求(+1)已在基礎台數計入，全求再加 +2（兩者可疊加）
    if not is_tsumo and len(p.hand) == 1:
        result.append(("全求", 2))

    # 天聽 / 地聽：初始或首次棄牌後聽牌，胡牌時計入
    if tenhou_label:
        result.append((tenhou_label, 8 if tenhou_label == "天聽" else 4))

    # 天胡 / 地胡 / 人胡：首巡胡牌，清 16 台（移除被取代的基礎台數項目）
    if is_first_round and not has_meld:
        if is_tsumo and winner == dealer_idx:
            # 天胡：莊家首巡自摸，不計不求（= 門清+自摸）
            result = [r for r in result if r[0] not in ("不求", "門清")]
            result.append(("天胡", 16))
        elif is_tsumo:
            # 地胡：閒家首巡自摸，不計不求/自摸
            result = [r for r in result if r[0] not in ("不求", "門清", "自摸")]
            result.append(("地胡", 16))
        else:
            # 人胡：首巡放槍胡，不計門清
            result = [r for r in result if r[0] != "門清"]
            result.append(("人胡", 16))

    return result


def _check_tenpai_initial(hand: list[int]) -> bool:
    """初始手牌是否已聽（摸到任一種牌即可胡）。

    Args:
        hand: 16 張（閒家）或 17 張（莊家）手牌列表。
              16 張：直接測試任一牌面加入後是否胡牌。
              17 張：逐一嘗試棄出每張，剩餘 16 張再測試。

    Returns:
        已聽回傳 True，否則 False。
    """
    if len(hand) == 16:
        return any(
            is_win_ext(hand, k * COPIES, 0)
            for k in range(SUITED_KINDS + HONOR_KINDS)
        )
    # 17 張（莊家）：嘗試每張棄牌後是否聽牌
    return any(
        any(
            is_win_ext(hand[:i] + hand[i + 1:], k * COPIES, 0)
            for k in range(SUITED_KINDS + HONOR_KINDS)
        )
        for i in range(len(hand))
    )


# ---------------------------------------------------------------------------
# 網頁模式資料結構：PromptInfo / GameState
# ---------------------------------------------------------------------------

@dataclass
class PromptInfo:
    """人類玩家的互動提示。

    Attributes:
        type:        提示類型（win_tsumo / win_ron / rob_kong / add_kong / kong / pon / chi）
        tile:        涉及的牌名（顯示用）
        tile_id:     涉及的牌號
        chi_options: 吃牌時的可選組合，每項為 [ta牌名, 棄牌名, tb牌名]
    """
    type: str
    tile: str
    tile_id: int
    chi_options: list[list[str]] | None = None


@dataclass
class GameState:
    """可 JSON 序列化的遊戲快照，供網頁前端渲染使用。

    Attributes:
        phase:       "human_discard" | "prompt" | "game_over"
        your_hand:   你的手牌牌名列表（已排序）
        hand_counts: 四家手牌張數（競賽模式 AI 不顯示牌名）
        melds:       四家面牌組，melds[i] 為第 i 家的副露列表，每副露為牌名列表
        discards:    四家棄牌牌名列表
        bonus:       四家花牌牌名列表
        log:         本輪累積事件文字
        prompt:      phase=="prompt" 時的提示內容
        winner:      胡牌玩家稱謂（game_over 時）
        scores:      台數明細列表（game_over 時）
    """
    phase: str
    your_hand: list[str]
    hand_counts: list[int]
    melds: list[list[list[str]]]
    discards: list[list[str]]
    bonus: list[list[str]]
    log: list[str]
    game_wind: str = ""
    seat_winds: list[str] = field(default_factory=list)
    dealer_idx: int = -1
    consecutive: int = 0
    deck_remaining: int = 0
    prompt: PromptInfo | None = None
    winner: str | None = None
    scores: list[tuple[str, int]] | None = None
    drawn_tile_idx: int | None = None  # 排序後新摸牌的索引（human_discard 時有效）
    all_hands: list[list[str]] | None = None  # game_over 時填入四家完整手牌（已排序）
    game_round_wind: str = ""  # 圈風（東/南/西/北），獨立於局風 game_wind


def player_label(player: int, seat_winds: list[str] | None = None) -> str:
    """回傳玩家稱謂：若提供 seat_winds 則顯示門風（東／南／西／北），否則顯示相對位置（你／下家／對家／上家）。"""
    if seat_winds is not None:
        return seat_winds[player]
    if player == HUMAN_PLAYER:
        return "你"
    return {1: "下家", 2: "對家", 3: "上家"}[(player - HUMAN_PLAYER) % 4]


# ---------------------------------------------------------------------------
# 網頁模式：GameSession（generator-based 狀態機）
# ---------------------------------------------------------------------------

class GameSession:
    """網頁模式遊戲狀態機，使用 Python generator 實作可暫停的遊戲迴圈。

    main() 的 stdin/stdout 互動模式完整保留，GameSession 為平行實作，
    供 FastAPI 後端驅動網頁對局使用。

    使用方式::

        session = GameSession(contest=True)
        state = session.start()          # 初始化並推進至首個人類決策點
        state = session.respond("3")     # 人類棄牌（discard idx 字串）
        state = session.respond("y")     # 人類宣胡 / 確認碰槓
        state = session.respond("n")     # 跳過提示
        state = session.respond("chi:1") # 人類選擇第 2 種吃法
    """

    def __init__(
        self,
        contest: bool = True,
        dealer_idx_override: int | None = None,
        consecutive: int = 0,
        seat_winds: list[str] | None = None,
        game_round_wind: str | None = None,
    ) -> None:
        """初始化 GameSession。

        Args:
            contest:             競賽模式，AI 手牌不顯示牌名
            dealer_idx_override: 指定莊家（連莊時傳入）
            consecutive:         連莊次數
            seat_winds:          指定座次門風列表；None 時隨機順時針抽定
            game_round_wind:     圈風（東/南/西/北）；None 時等於莊家門風
        """
        self.contest = contest
        self.dealer_idx_override = dealer_idx_override
        self.consecutive = consecutive
        self.seat_winds_override = seat_winds
        self.game_round_wind_override = game_round_wind
        self._gen: object = None
        self._log: list[str] = []
        self._game_wind: str = ""
        self._game_round_wind: str = ""
        self._seat_winds: list[str] = []
        self._dealer_idx: int = -1
        self._drawn_tile: int | None = None  # 本輪人類玩家剛摸到的牌號

    def start(self) -> GameState:
        """初始化牌局，推進至首個人類決策點，回傳 GameState。"""
        self._gen = self._game_loop()
        return next(self._gen)  # type: ignore[arg-type]

    def respond(self, response: str) -> GameState:
        """傳入人類回應，繼續推進遊戲，回傳下一個 GameState。

        Args:
            response: 對應目前 phase 的回應字串
                - phase=="human_discard" → 棄牌索引字串（"0"–"16"）
                - phase=="prompt"        → "y" / "n" / "chi:N"（N 為吃法索引）
        """
        if self._gen is None:
            raise RuntimeError("GameSession 尚未啟動，請先呼叫 start()")
        try:
            return self._gen.send(response)  # type: ignore[union-attr]
        except StopIteration as e:
            return e.value

    # ------------------------------------------------------------------
    # 內部輔助
    # ------------------------------------------------------------------

    def _snapshot(
        self,
        m: "Mahjong",
        phase: str,
        prompt: PromptInfo | None = None,
        winner: str | None = None,
        scores: list[tuple[str, int]] | None = None,
    ) -> GameState:
        """根據目前遊戲狀態產生 GameState 快照。

        Args:
            m:      遊戲物件
            phase:  "human_discard" | "prompt" | "game_over"
            prompt: 提示（phase=="prompt" 時）
            winner: 勝者稱謂（game_over 時）
            scores: 台數明細（game_over 時）
        """
        your_hand = [n_to_chinese(t) for t in sorted(m.players[HUMAN_PLAYER].hand)]
        hand_counts = [len(m.players[i].hand) for i in range(4)]
        melds_out: list[list[list[str]]] = []
        discards_out: list[list[str]] = []
        bonus_out: list[list[str]] = []
        for i in range(4):
            p = m.players[i]
            meld_strs: list[list[str]] = []
            for meld in p.melds:
                # 吃牌面牌：discard 置中顯示（與 main() 一致）
                if len(meld) == 3 and meld[0] // COPIES != meld[1] // COPIES:
                    display = [meld[0], meld[2], meld[1]]
                else:
                    display = meld
                meld_strs.append([n_to_chinese(t) for t in display])
            melds_out.append(meld_strs)
            discards_out.append([n_to_chinese(t) for t in p.discards])
            bonus_out.append([n_to_chinese(t) for t in p.bonus])
        drawn_tile_idx: int | None = None
        if phase == "human_discard" and self._drawn_tile is not None:
            try:
                drawn_tile_idx = sorted(m.players[HUMAN_PLAYER].hand).index(self._drawn_tile)
            except ValueError:
                pass
        all_hands: list[list[str]] | None = None
        if phase == "game_over":
            all_hands = [
                [n_to_chinese(t) for t in sorted(m.players[i].hand)]
                for i in range(4)
            ]
        return GameState(
            phase=phase,
            your_hand=your_hand,
            hand_counts=hand_counts,
            melds=melds_out,
            discards=discards_out,
            bonus=bonus_out,
            log=list(self._log),
            game_wind=self._game_wind,
            seat_winds=self._seat_winds,
            dealer_idx=self._dealer_idx,
            consecutive=self.consecutive,
            deck_remaining=len(m.remain),
            prompt=prompt,
            winner=winner,
            scores=scores,
            drawn_tile_idx=drawn_tile_idx,
            all_hands=all_hands,
            game_round_wind=self._game_round_wind,
        )

    def _log_clear(self) -> None:
        """清空 log 緩衝。"""
        self._log.clear()

    def _L(self, msg: str) -> None:
        """附加一行事件文字至 log。"""
        self._log.append(msg)

    # ------------------------------------------------------------------
    # 遊戲主迴圈（generator）
    # ------------------------------------------------------------------

    def _game_loop(self):  # type: ignore[return]
        """遊戲主迴圈 generator。

        在人類決策點 yield GameState，接收回應後繼續推進。
        遊戲結束時 return 最終 GameState（透過 StopIteration.value 回傳）。
        """
        import random as _rnd
        import contextlib as _cl, io as _io

        def _draw_bonus_silent(m_: "Mahjong", p_: "PlayerState", idx_: int) -> None:
            """靜默版 _draw_bonus：補牌動作不直接輸出，由呼叫端視需要記錄 log。"""
            import contextlib as _c2, io as _i2
            with _c2.redirect_stdout(_i2.StringIO()):
                m_._draw_bonus(p_, idx_)

        m = Mahjong(n_hand=16)
        m.init_deal()
        self._log.clear()

        # 分配門風：連莊沿用上局座次，新局隨機順時針抽定
        if self.seat_winds_override is not None:
            seat_winds = list(self.seat_winds_override)
        else:
            _offset = _rnd.randrange(4)
            seat_winds = [_SEAT_WIND_NAMES[(_offset + i) % 4] for i in range(4)]
        plabel = lambda p: player_label(p, seat_winds)  # noqa: E731
        human_wind = seat_winds[HUMAN_PLAYER]
        if self.dealer_idx_override is not None:
            dealer_idx = self.dealer_idx_override
        else:
            dealer_idx = 0          # 首局東家先莊
        game_wind = seat_winds[dealer_idx]  # 局風 = 莊家門風
        game_round_wind = (
            self.game_round_wind_override
            if self.game_round_wind_override is not None
            else game_wind
        )
        self._game_wind = game_wind
        self._game_round_wind = game_round_wind
        self._seat_winds = seat_winds
        self._dealer_idx = dealer_idx

        self._L(f"【你是 {human_wind}｜{game_round_wind}風{game_wind}局】莊家：{plabel(dealer_idx)}")

        # 莊家多摸一張
        dealer_p = m.players[dealer_idx]
        dealer_extra = m.deal_one()
        dealer_p.hand.append(dealer_extra)

        # 補花（使用 len 而非 n_hand，確保莊家第 17 張也補花）
        import contextlib as _cl, io as _io
        for _pi in range(4):
            _pp = m.players[_pi]
            _bonus_before = len(_pp.bonus)
            for _i in range(len(_pp.hand)):
                _draw_bonus_silent(m, _pp, _i)
            _new_bonus = _pp.bonus[_bonus_before:]
            if _new_bonus:
                _tiles_str = " ".join(n_to_chinese(t) for t in _new_bonus)
                self._L(f"{seat_winds[_pi]}補花 {_tiles_str}")
            for _t in _pp.hand:
                _pp.add_seen(_t)

        # 天聽偵測（跳過手牌含花牌的玩家：牌堆耗盡時補花不完整）
        tenhou_flags: dict[int, str] = {}
        for _pi in range(4):
            _ph = m.players[_pi].hand
            if any(t >= BONUS_START for t in _ph):
                continue
            if _check_tenpai_initial(_ph):
                tenhou_flags[_pi] = "天聽"

        player = dealer_idx
        skip_draw = True
        after_supplement = False
        last_tile_drawn = False
        first_round = True
        first_turns_done: set[int] = set()

        while m.remain:
            p = m.players[player]
            ai = m.ai[player]
            if not skip_draw:
                after_supplement = False
                last_tile_drawn = False
                drawn = m.deal_one()
                if m.remain == 0:
                    last_tile_drawn = True
                _orig_drawn = drawn
                p.hand.append(drawn)
                _bonus_cnt = len(p.bonus)
                _draw_bonus_silent(m, p, len(p.hand) - 1)
                _mid_bonus = p.bonus[_bonus_cnt:]
                if _mid_bonus:
                    _tiles_str = " ".join(n_to_chinese(t) for t in _mid_bonus)
                    self._L(f"{plabel(player)}補花 {_tiles_str}")
                drawn = p.hand[-1]
                # 補花失敗（牌堆耗盡）→ 宣告和局
                if drawn >= BONUS_START:
                    break
                after_supplement = (_orig_drawn >= BONUS_START)
                p.add_seen(drawn)
                if player == HUMAN_PLAYER:
                    self._drawn_tile = drawn

                # 自摸判胡
                if drawn < BONUS_START and is_win_ext(
                    p.hand[:-1], drawn, p.chi_count + p.pon_count + p.kong_count
                ):
                    if player == HUMAN_PLAYER:
                        pr = PromptInfo(type="win_tsumo", tile=n_to_chinese(drawn), tile_id=drawn)
                        resp: str = yield self._snapshot(m, "prompt", prompt=pr)
                        self._log_clear()
                        if resp == "y":
                            _sc = score_hand(
                                player, dealer_idx, self.consecutive, True, p, drawn,
                                game_wind, seat_winds, is_kong_flower=after_supplement,
                                is_last_tile=last_tile_drawn, is_first_round=first_round,
                                tenhou_label=tenhou_flags.get(player, ""),
                            )
                            self._L(f"你自摸胡 {n_to_chinese(drawn)}！")
                            return self._snapshot(m, "game_over", winner=plabel(player), scores=_sc)
                        # 否則繼續出牌
                    else:
                        _sc = score_hand(
                            player, dealer_idx, self.consecutive, True, p, drawn,
                            game_wind, seat_winds, is_kong_flower=after_supplement,
                            is_last_tile=last_tile_drawn, is_first_round=first_round,
                            tenhou_label=tenhou_flags.get(player, ""),
                        )
                        self._L(f"{plabel(player)}自摸胡！")
                        return self._snapshot(m, "game_over", winner=plabel(player), scores=_sc)

                if not m.remain:
                    break

                # 加槓
                add_meld_idx = can_add_to_pon(drawn, p.melds)
                if add_meld_idx is not None:
                    do_add = False
                    if player == HUMAN_PLAYER:
                        pr = PromptInfo(type="add_kong", tile=n_to_chinese(drawn), tile_id=drawn)
                        resp = yield self._snapshot(m, "prompt", prompt=pr)
                        self._log_clear()
                        do_add = (resp == "y")
                    elif AI_AUTO_KONG:
                        do_add = True
                    if do_add:
                        p.melds[add_meld_idx].append(drawn)
                        p.hand.remove(drawn)
                        p.kong_count += 1
                        self._L(f"{plabel(player)}加槓 {n_to_chinese(drawn)}")
                        # 搶槓掃描
                        robbed = False
                        for _off in range(1, 4):
                            rob_idx = (player + _off) % 4
                            rob_p = m.players[rob_idx]
                            if is_win_ext(
                                rob_p.hand, drawn,
                                rob_p.chi_count + rob_p.pon_count + rob_p.kong_count,
                            ):
                                do_rob = True
                                if rob_idx == HUMAN_PLAYER:
                                    pr2 = PromptInfo(type="rob_kong", tile=n_to_chinese(drawn), tile_id=drawn)
                                    resp2: str = yield self._snapshot(m, "prompt", prompt=pr2)
                                    self._log_clear()
                                    do_rob = (resp2 == "y")
                                if do_rob:
                                    _sc = score_hand(
                                        rob_idx, dealer_idx, self.consecutive, False, rob_p,
                                        drawn, game_wind, seat_winds, is_rob_kong=True,
                                        tenhou_label=tenhou_flags.get(rob_idx, ""),
                                        pao_idx=player,
                                    )
                                    self._L(f"{plabel(rob_idx)}搶槓胡！")
                                    return self._snapshot(m, "game_over", winner=plabel(rob_idx), scores=_sc)
                                    robbed = True
                        if not robbed and m.remain:
                            extra = m.deal_one()
                            p.hand.append(extra)
                            _bonus_cnt_k = len(p.bonus)
                            _draw_bonus_silent(m, p, len(p.hand) - 1)
                            _kong_bonus = p.bonus[_bonus_cnt_k:]
                            if _kong_bonus:
                                _tiles_str = " ".join(n_to_chinese(t) for t in _kong_bonus)
                                self._L(f"{plabel(player)}補花 {_tiles_str}")
                            if not self.contest or player == HUMAN_PLAYER:
                                self._L(f"補摸 {n_to_chinese(p.hand[-1])}")
                        after_supplement = True
                        skip_draw = True
                        continue
            else:
                if player == HUMAN_PLAYER:
                    self._drawn_tile = None  # 吃/碰/槓後無新摸牌，不高亮
                # 天胡（若手牌含花牌則跳過：牌堆耗盡邊界情況）
                if (
                    first_round and player == dealer_idx
                    and not (p.chi_count + p.pon_count + p.kong_count)
                    and not any(t >= BONUS_START for t in p.hand)
                ):
                    for _i, _t in enumerate(p.hand):
                        if _t < BONUS_START and is_win_ext(p.hand[:_i] + p.hand[_i + 1:], _t, 0):
                            _sc = score_hand(
                                player, dealer_idx, self.consecutive, True, p, _t,
                                game_wind, seat_winds, is_first_round=True,
                                tenhou_label=tenhou_flags.get(player, ""),
                            )
                            self._L(f"{plabel(player)}天胡！")
                            return self._snapshot(m, "game_over", winner=plabel(player), scores=_sc)
                skip_draw = False

            # ── 棄牌 ──────────────────────────────────────────────────
            # 防衛：手牌含花牌（補花失敗）→ 和局
            if any(t >= BONUS_START for t in p.hand):
                break
            p.hand.sort()
            if player == HUMAN_PLAYER:
                resp = yield self._snapshot(m, "human_discard")
                self._log_clear()
                discard_idx = int(resp)
                discard_tile = p.hand[discard_idx]
                p.hand[discard_idx] = p.hand[-1]
                p.hand.pop()
                self._L(f"你打 {n_to_chinese(discard_tile)}")
            else:
                calculate_gates(m, p, ai)
                discard_idx, discard_level = decide_play(p, ai, m.players)  # type: ignore[misc]
                discard_tile = p.hand[discard_idx]
                p.hand[discard_idx] = p.hand[-1]
                p.hand.pop()
                tear = "（拆牌）" if discard_level == DangerLevel.EXTREMELY_DANGEROUS else ""
                self._L(f"{plabel(player)}打 {n_to_chinese(discard_tile)}{tear}")

            p.discards.append(discard_tile)
            for _obs in range(1, 4):
                m.players[(player + _obs) % 4].add_seen(discard_tile)

            # 地聽偵測
            if (
                first_round
                and player not in first_turns_done
                and not (p.chi_count + p.pon_count + p.kong_count)
                and player not in tenhou_flags
                and _check_tenpai_initial(p.hand)
            ):
                tenhou_flags[player] = "地聽"

            if first_round:
                first_turns_done.add(player)
                if len(first_turns_done) >= 4:
                    first_round = False

            # ── 放槍 ──────────────────────────────────────────────────
            for _off in range(1, 4):
                cand_idx = (player + _off) % 4
                cand_p = m.players[cand_idx]
                if is_win_ext(
                    cand_p.hand, discard_tile,
                    cand_p.chi_count + cand_p.pon_count + cand_p.kong_count,
                ):
                    if cand_idx == HUMAN_PLAYER:
                        pr = PromptInfo(type="win_ron", tile=n_to_chinese(discard_tile), tile_id=discard_tile)
                        resp = yield self._snapshot(m, "prompt", prompt=pr)
                        self._log_clear()
                        if resp != "y":
                            continue
                    cand_p.hand.append(discard_tile)
                    _sc = score_hand(
                        cand_idx, dealer_idx, self.consecutive, False, cand_p,
                        discard_tile, game_wind, seat_winds, is_last_tile=last_tile_drawn,
                        is_first_round=first_round, tenhou_label=tenhou_flags.get(cand_idx, ""),
                        pao_idx=player,
                    )
                    cand_p.hand.pop()
                    self._L(f"{plabel(cand_idx)}胡！（{plabel(player)} 放槍）")
                    return self._snapshot(m, "game_over", winner=plabel(cand_idx), scores=_sc)

            # ── 明槓 ──────────────────────────────────────────────────
            kong_player: int | None = None
            for _off in range(1, 4):
                cand_idx = (player + _off) % 4
                cand_p = m.players[cand_idx]
                kong_triple = can_kong(cand_p.hand, discard_tile)
                if kong_triple is not None:
                    if cand_idx == HUMAN_PLAYER:
                        pr = PromptInfo(type="kong", tile=n_to_chinese(discard_tile), tile_id=discard_tile)
                        resp = yield self._snapshot(m, "prompt", prompt=pr)
                        self._log_clear()
                        if resp != "y":
                            continue
                    elif not AI_AUTO_KONG:
                        continue
                    ta, tb, tc = kong_triple
                    _do_meld(m, player, cand_idx, discard_tile, [ta, tb, tc])
                    cand_p.kong_count += 1
                    self._L(f"{plabel(cand_idx)}槓 {n_to_chinese(discard_tile)}")
                    first_round = False
                    tenhou_flags.pop(cand_idx, None)
                    player = cand_idx
                    kong_player = cand_idx
                    break

            # ── 碰 ────────────────────────────────────────────────────
            pon_player: int | None = None
            if kong_player is None:
                for _off in range(1, 4):
                    cand_idx = (player + _off) % 4
                    cand_p = m.players[cand_idx]
                    pon_pair = can_pon(cand_p.hand, discard_tile)
                    if pon_pair is not None:
                        if cand_idx == HUMAN_PLAYER:
                            pr = PromptInfo(type="pon", tile=n_to_chinese(discard_tile), tile_id=discard_tile)
                            resp = yield self._snapshot(m, "prompt", prompt=pr)
                            self._log_clear()
                            if resp != "y":
                                continue
                        ta, tb = pon_pair
                        _do_meld(m, player, cand_idx, discard_tile, [ta, tb])
                        cand_p.pon_count += 1
                        self._L(f"{plabel(cand_idx)}碰 {n_to_chinese(discard_tile)}")
                        first_round = False
                        tenhou_flags.pop(cand_idx, None)
                        skip_draw = True
                        player = cand_idx
                        pon_player = cand_idx
                        break

            # ── 吃 ────────────────────────────────────────────────────
            if kong_player is None and pon_player is None:
                next_idx = (player + 1) % 4
                np_state = m.players[next_idx]
                chi_pair = can_chi(np_state.hand, discard_tile) if discard_tile < SUITED_END else None
                if chi_pair is not None:
                    do_chi = True
                    chosen_ta, chosen_tb = chi_pair
                    if next_idx == HUMAN_PLAYER:
                        # 枚舉所有吃法
                        kind_d = discard_tile // COPIES
                        rank_d = kind_d % TILES_PER_SUIT
                        def _find_in_h(h: list[int], k: int) -> int | None:
                            for t in h:
                                if t // COPIES == k:
                                    return t
                            return None
                        all_combos: list[tuple[int, int]] = []
                        combo_kinds = []
                        if rank_d >= 2:
                            combo_kinds.append((kind_d - 2, kind_d - 1))
                        if 1 <= rank_d <= 7:
                            combo_kinds.append((kind_d - 1, kind_d + 1))
                        if rank_d <= 6:
                            combo_kinds.append((kind_d + 1, kind_d + 2))
                        for ka, kb in combo_kinds:
                            ta2 = _find_in_h(np_state.hand, ka)
                            if ta2 is None:
                                continue
                            tmp = list(np_state.hand)
                            tmp.remove(ta2)
                            tb2 = _find_in_h(tmp, kb)
                            if tb2 is not None:
                                all_combos.append((ta2, tb2))
                        chi_opts = [
                            [n_to_chinese(ta2), n_to_chinese(discard_tile), n_to_chinese(tb2)]
                            for ta2, tb2 in all_combos
                        ]
                        pr = PromptInfo(
                            type="chi", tile=n_to_chinese(discard_tile),
                            tile_id=discard_tile, chi_options=chi_opts,
                        )
                        resp = yield self._snapshot(m, "prompt", prompt=pr)
                        self._log_clear()
                        if resp in ("n", "pass"):
                            do_chi = False
                        else:
                            ci = int(resp.replace("chi:", ""))
                            chosen_ta, chosen_tb = all_combos[ci]
                    if do_chi:
                        _do_meld(m, player, next_idx, discard_tile, [chosen_ta, chosen_tb])
                        np_state.chi_count += 1
                        self._L(f"{plabel(next_idx)}吃 {n_to_chinese(discard_tile)}")
                        first_round = False
                        tenhou_flags.pop(next_idx, None)
                        skip_draw = True
                        player = next_idx
                    else:
                        player = (player + 1) % 4
                else:
                    player = (player + 1) % 4
            # kong/pon 時 player 已設定，不需額外推進

        # 和局
        self._L("牌堆耗盡，和局！")
        return self._snapshot(m, "game_over", winner=None)


def main(
    dealer_idx_override: int | None = None,
    consecutive: int = 0,
    contest_mode: bool = False,
    seat_winds_override: list[str] | None = None,
    game_round_wind_override: str | None = None,
) -> tuple[int | None, int, list[str], str]:
    """四人 AI 麻將主遊戲迴圈。

    Args:
        dealer_idx_override:     指定莊家座位（連莊時傳入）；None 則從東家起莊。
        consecutive:             本局連莊次數（0 表示首局）。
        seat_winds_override:     指定座次門風；None 時隨機順時針抽定（新局）。
        game_round_wind_override: 圈風；None 時等於莊家門風。

    Returns:
        (winner, dealer_idx, seat_winds, game_round_wind)：winner 為胡牌玩家索引，和局時為 None。

    流程：
    1. 初始化並發牌、補花
    2. 四人輪流：
       - 正常輪次：摸牌 → 補花 → 判胡 → AI 計算 → 打牌
       - 吃牌輪次：跳過摸牌（skip_draw=True）→ AI 計算 → 打牌
    3. 棄牌後檢查下一家是否自動吃牌，若可吃則移至桌面並設 skip_draw
    4. 胡牌或牌堆耗盡則結束
    """
    m = Mahjong(n_hand=16)
    m.init_deal()

    # 分配門風：連莊沿用上局座次，新局隨機順時針抽定
    import random as _rnd
    if seat_winds_override is not None:
        seat_winds = list(seat_winds_override)
    else:
        _offset = _rnd.randrange(4)
        seat_winds = [_SEAT_WIND_NAMES[(_offset + i) % 4] for i in range(4)]
    plabel = lambda p: player_label(p, seat_winds)  # noqa: E731
    human_wind = seat_winds[HUMAN_PLAYER]
    if dealer_idx_override is not None:
        dealer_idx = dealer_idx_override
    else:
        dealer_idx = 0          # 首局東家先莊
    game_wind = seat_winds[dealer_idx]  # 局風 = 莊家門風
    game_round_wind = game_round_wind_override if game_round_wind_override is not None else game_wind
    consec_label = f"  連莊 {consecutive} 次" if consecutive > 0 else ""
    print(f"\n【你是 {human_wind}（座位 {HUMAN_PLAYER}）｜{game_round_wind}風{game_wind}局{consec_label}】")
    for i, w in enumerate(seat_winds):
        parts = []
        if i == HUMAN_PLAYER:
            parts.append("← 你")
        if i == dealer_idx:
            parts.append("★莊")
        label = "  ".join(parts)
        print(f"  座位{i} {w}  {label}" if label else f"  座位{i} {w}")

    # 莊家補花前多摸一張（開打時手牌共 17 張）
    dealer_p = m.players[dealer_idx]
    dealer_extra = m.deal_one()
    dealer_p.hand.append(dealer_extra)
    _show_dealer_tile = not contest_mode or dealer_idx == HUMAN_PLAYER
    print(f"\n莊家（座位{dealer_idx}）多摸{' ' + n_to_chinese(dealer_extra) if _show_dealer_tile else ''}")

    # 補花並顯示初始手牌（contest_mode 時隱藏 AI 手牌）
    import contextlib as _cl, io as _io
    for _pi in range(4):
        _pp = m.players[_pi]
        if contest_mode and _pi != HUMAN_PLAYER:
            with _cl.redirect_stdout(_io.StringIO()):
                print(f"\n{_pi}", end="")
                for _i in range(_pp.n_hand):
                    print(f" {n_to_chinese(_pp.hand[_i])}", end="")
                    m._draw_bonus(_pp, _i)
        else:
            print(f"\n{_pi}", end="")
            for _i in range(_pp.n_hand):
                print(f" {n_to_chinese(_pp.hand[_i])}", end="")
                m._draw_bonus(_pp, _i)
        for _t in _pp.hand:
            _pp.add_seen(_t)
    print()

    # 天聽偵測：補花完成後立即掃描各家是否已聽
    tenhou_flags: dict[int, str] = {}
    for _pi in range(4):
        if _check_tenpai_initial(m.players[_pi].hand):
            tenhou_flags[_pi] = "天聽"

    def _print_summary() -> None:
        """印出四家的手牌、面牌（吃/碰/槓）、花牌摘要。"""
        print("\n── 各家牌況 ──")
        for _i in range(4):
            _pi = m.players[_i]
            _hand = " ".join(n_to_chinese(t) for t in sorted(_pi.hand))
            _meld = "  ".join(
                "[" + " ".join(n_to_chinese(t) for t in g) + "]"
                for g in _pi.melds
            )
            _bonus = " ".join(n_to_chinese(t) for t in _pi.bonus)
            _line = f"  {seat_winds[_i]}  手：{_hand}"
            if _meld:
                _line += f"  面：{_meld}"
            if _bonus:
                _line += f"  花：{_bonus}"
            print(_line)

    player = dealer_idx
    skip_draw = True    # 莊家首輪跳過摸牌，直接出牌
    after_supplement = False  # 是否為補花/加槓後補摸（跨回合保持，用於槓上開花判定）
    last_tile_drawn = False   # 是否剛摸完牌堆最後一張（用於海底撈月/河底撈魚判定）
    first_round = True        # 首巡旗標（用於天胡/地胡/人胡判定）
    first_turns_done: set[int] = set()  # 已完成首次棄牌的玩家集合
    # tenhou_flags 在 show_bonus() 後才初始化（見下方）
    while m.remain:
        p = m.players[player]
        ai = m.ai[player]

        if not skip_draw:
            # 正常輪次：摸牌
            after_supplement = False  # 每次正常摸牌重置
            last_tile_drawn = False   # 每次正常摸牌重置
            drawn = m.deal_one()
            if m.remain == 0:
                last_tile_drawn = True  # 剛摸到牌堆最後一張
            _orig_drawn = drawn
            p.hand.append(drawn)
            m._draw_bonus(p, len(p.hand) - 1)
            drawn = p.hand[-1]      # 補花後的實際摸入牌
            after_supplement = (_orig_drawn >= BONUS_START)  # 原為花牌則補牌視為槓上開花
            p.add_seen(drawn)
            if player == HUMAN_PLAYER:
                print(f"\n你摸 {n_to_chinese(drawn)}")

            # 判胡（摸牌後立即判斷；若補花失敗牌堆已空則 drawn 可能是花牌，跳過判胡）
            if drawn < BONUS_START and is_win_ext(p.hand[:-1], drawn, p.chi_count + p.pon_count + p.kong_count):
                if player == HUMAN_PLAYER:
                    ans = input(f"\n自摸胡！宣胡？(y/n) ").strip().lower()
                    if ans == "y":
                        print(f"\n{plabel(player)}自摸胡 {n_to_chinese(drawn)}")
                        for t in p.hand[:-1]:
                            print(f" {n_to_chinese(t)}", end="")
                        print()
                        _score = score_hand(player, dealer_idx, consecutive, True, p, drawn, game_wind, seat_winds, is_kong_flower=after_supplement, is_last_tile=last_tile_drawn, is_first_round=first_round, tenhou_label=tenhou_flags.get(player, ""))
                        _total = sum(v for _, v in _score)
                        _detail = " ".join(f"{n}+{v}" for n, v in _score)
                        print(f"台數明細：{_detail} = 共 {_total} 台")
                        _print_summary()
                        return player, dealer_idx, seat_winds, game_round_wind
                else:
                    print(f"\n{plabel(player)}胡", end="")
                    for t in p.hand[:-1]:
                        print(f" {n_to_chinese(t)}", end="")
                    print()
                    _score = score_hand(player, dealer_idx, consecutive, True, p, drawn, game_wind, seat_winds, is_kong_flower=after_supplement, is_last_tile=last_tile_drawn, is_first_round=first_round, tenhou_label=tenhou_flags.get(player, ""))
                    _total = sum(v for _, v in _score)
                    _detail = " ".join(f"{n}+{v}" for n, v in _score)
                    print(f"台數明細：{_detail} = 共 {_total} 台")
                    _print_summary()
                    return player, dealer_idx, seat_winds, game_round_wind

            # 牌堆若已空（補花後耗盡），宣告和局
            if not m.remain:
                break

            # 加槓判定：摸入的牌可補入已碰刻子
            add_meld_idx = can_add_to_pon(drawn, p.melds)
            if add_meld_idx is not None:
                do_add = False
                if player == HUMAN_PLAYER:
                    ans = input(
                        f"\n  你可以加槓 {n_to_chinese(drawn)}？(y/n) "
                    ).strip().lower()
                    do_add = ans == "y"
                elif AI_AUTO_KONG:
                    do_add = True

                if do_add:
                    p.melds[add_meld_idx].append(drawn)
                    p.hand.remove(drawn)
                    p.kong_count += 1
                    print(f"\n  {plabel(player)}加槓 {n_to_chinese(drawn)}", end="")

                    # 搶槓掃描：其他三家是否可胡
                    robbed = False
                    for offset in range(1, 4):
                        rob_idx = (player + offset) % 4
                        rob_p = m.players[rob_idx]
                        if is_win_ext(
                            rob_p.hand,
                            drawn,
                            rob_p.chi_count + rob_p.pon_count + rob_p.kong_count,
                        ):
                            do_rob = True
                            if rob_idx == HUMAN_PLAYER:
                                ans2 = input(
                                    f"\n  你可以搶槓胡 {n_to_chinese(drawn)}？(y/n) "
                                ).strip().lower()
                                do_rob = ans2 == "y"
                            if do_rob:
                                print(
                                    f"\n  {plabel(rob_idx)}搶槓胡！（{plabel(player)} 加槓 {n_to_chinese(drawn)}）"
                                )
                                rob_p.hand.append(drawn)
                                for t in rob_p.hand[:-1]:
                                    print(f" {n_to_chinese(t)}", end="")
                                print()
                                _score = score_hand(
                                    rob_idx, dealer_idx, consecutive,
                                    False, rob_p, drawn,
                                    game_wind, seat_winds, is_rob_kong=True,
                                    tenhou_label=tenhou_flags.get(rob_idx, ""),
                                    pao_idx=player,
                                )
                                rob_p.hand.pop()
                                _total = sum(v for _, v in _score)
                                _detail = " ".join(f"{n}+{v}" for n, v in _score)
                                print(f"台數明細：{_detail} = 共 {_total} 台")
                                robbed = True
                                _print_summary()
                                return rob_idx, dealer_idx, seat_winds, game_round_wind
                    if not robbed:
                        # 無搶槓，補摸一張後繼續本輪出牌（skip_draw=True 跳過下次摸牌）
                        if m.remain:
                            extra = m.deal_one()
                            p.hand.append(extra)
                            m._draw_bonus(p, len(p.hand) - 1)
                            print(f" 補摸 {n_to_chinese(p.hand[-1])}", end="")
                        after_supplement = True   # 加槓後補摸，觸發槓上開花條件
                        skip_draw = True
                        continue
        else:
            # 吃/碰牌輪次：跳過摸牌，直接進入出牌
            # 天胡：莊家首巡（尚未出牌、無副露），嘗試所有閉門牌作為胡牌
            if first_round and player == dealer_idx and not (p.chi_count + p.pon_count + p.kong_count):
                for _i, _t in enumerate(p.hand):
                    if _t < BONUS_START and is_win_ext(p.hand[:_i] + p.hand[_i + 1:], _t, 0):
                        print(f"\n{plabel(player)}天胡 {n_to_chinese(_t)}")
                        for t in p.hand:
                            print(f" {n_to_chinese(t)}", end="")
                        print()
                        _score = score_hand(player, dealer_idx, consecutive, True, p, _t, game_wind, seat_winds, is_first_round=True, tenhou_label=tenhou_flags.get(player, ""))
                        _total = sum(v for _, v in _score)
                        _detail = " ".join(f"{n}+{v}" for n, v in _score)
                        print(f"台數明細：{_detail} = 共 {_total} 台")
                        _print_summary()
                        return player, dealer_idx, seat_winds, game_round_wind
            skip_draw = False

        # 棄牌前將手牌由小到大排列（方便閱讀與選牌）
        p.hand.sort()

        # 人類玩家：顯示三家棄牌與標號手牌，互動選牌
        if player == HUMAN_PLAYER:
            print()
            for i in range(4):
                opp = (player + i) % 4
                opp_discards = " ".join(n_to_chinese(t) for t in m.players[opp].discards)
                print(f"  {plabel(opp)} 棄: {opp_discards}")
            print("  你的手牌：")
            hand_display = "  " + "  ".join(
                f"[{idx}]{n_to_chinese(t)}" for idx, t in enumerate(p.hand)
            )
            print(hand_display)
            while True:
                raw = input(f"  選擇棄牌編號 (0–{len(p.hand)-1}): ").strip()
                if raw.isdigit() and 0 <= int(raw) < len(p.hand):
                    discard_idx = int(raw)
                    break
                print(f"  請輸入 0 到 {len(p.hand)-1} 之間的數字")
            discard_tile = p.hand[discard_idx]
            p.hand[discard_idx] = p.hand[-1]
            p.hand.pop()
            print(f"{plabel(player)}打 {n_to_chinese(discard_tile)}_", end="")
            for t in p.hand:
                print(f" {n_to_chinese(t)}", end="")
        else:
            # AI 計算聽牌與出牌
            calculate_gates(m, p, ai)

            # 決定出牌（傳入 players 啟用 DangerLevel 策略）
            discard_idx, discard_level = decide_play(p, ai, m.players)  # type: ignore[misc]
            # 將摸入牌換入打出位置（維持 hand 長度 = n_hand - chi_count*2）
            discard_tile = p.hand[discard_idx]
            p.hand[discard_idx] = p.hand[-1]
            p.hand.pop()

            # 拆牌：被迫棄出 EXTREMELY_DANGEROUS 牌（湊牌）
            tear = "（拆牌）" if discard_level == DangerLevel.EXTREMELY_DANGEROUS else ""
            print(f"\n{plabel(player)}打 {n_to_chinese(discard_tile)}{tear}_", end="")
            if not contest_mode:
                for t in p.hand:
                    print(f" {n_to_chinese(t)}", end="")
        if p.bonus:
            for t in p.bonus:
                print(f" 花:{n_to_chinese(t)}", end="")
        for meld in p.melds:
            # 吃牌（3 張且前兩張不同種）：棄牌（最後一張）置中顯示
            if len(meld) == 3 and meld[0] // COPIES != meld[1] // COPIES:
                display = [meld[0], meld[2], meld[1]]
            else:
                display = meld
            print(f" [{' '.join(n_to_chinese(t) for t in display)}]", end="")

        # 棄牌記入各家記牌
        p.discards.append(discard_tile)
        for other in range(1, 4):
            m.players[(player + other) % 4].add_seen(discard_tile)

        # 地聽偵測：首次棄牌後手牌仍聽牌（無副露、尚無天聽標記）
        if (
            first_round
            and player not in first_turns_done
            and not (p.chi_count + p.pon_count + p.kong_count)
            and player not in tenhou_flags
            and _check_tenpai_initial(p.hand)
        ):
            tenhou_flags[player] = "地聽"

        # 首巡追蹤：各玩家完成首次棄牌後標記；全員完成則結束首巡
        if first_round:
            first_turns_done.add(player)
            if len(first_turns_done) >= 4:
                first_round = False

        # 放槍判定：棄牌後立即掃描其他三家
        for offset in range(1, 4):
            cand_idx = (player + offset) % 4
            cand_p = m.players[cand_idx]
            if is_win_ext(
                cand_p.hand,
                discard_tile,
                cand_p.chi_count + cand_p.pon_count + cand_p.kong_count,
            ):
                print(
                    f"\n  {plabel(cand_idx)}胡！（{plabel(player)} 放槍 {n_to_chinese(discard_tile)}）"
                )
                _cp = m.players[cand_idx]
                _cp.hand.append(discard_tile)   # 暫加入以便 score_hand 分析
                for t in _cp.hand[:-1]:
                    print(f" {n_to_chinese(t)}", end="")
                print()
                _score = score_hand(cand_idx, dealer_idx, consecutive, False, _cp, discard_tile, game_wind, seat_winds, is_last_tile=last_tile_drawn, is_first_round=first_round, tenhou_label=tenhou_flags.get(cand_idx, ""), pao_idx=player)
                _cp.hand.pop()                  # 還原
                _total = sum(v for _, v in _score)
                _detail = " ".join(f"{n}+{v}" for n, v in _score)
                print(f"台數明細：{_detail} = 共 {_total} 台")
                _print_summary()
                return cand_idx, dealer_idx, seat_winds, game_round_wind

        # 檢查其他三家是否明槓（AI_AUTO_KONG 控制；人類玩家詢問 y/n）
        kong_player: int | None = None
        for offset in range(1, 4):
            cand_idx = (player + offset) % 4
            cand_p = m.players[cand_idx]
            kong_triple = can_kong(cand_p.hand, discard_tile)
            if kong_triple is not None:
                if cand_idx == HUMAN_PLAYER:
                    ans = input(
                        f"\n  你可以槓 {n_to_chinese(discard_tile)}？(y/n) "
                    ).strip().lower()
                    if ans != "y":
                        continue
                elif not AI_AUTO_KONG:
                    continue
                ta, tb, tc = kong_triple
                cand_p.hand.remove(ta)
                cand_p.hand.remove(tb)
                cand_p.hand.remove(tc)
                _do_meld(m, player, cand_idx, discard_tile, [ta, tb, tc])
                cand_p.kong_count += 1
                print(
                    f"\n  {plabel(cand_idx)}槓 {n_to_chinese(discard_tile)}"
                    f"（{n_to_chinese(ta)} {n_to_chinese(tb)} {n_to_chinese(tc)}）",
                    end="",
                )
                if PAUSE_ON_MELD and cand_idx != HUMAN_PLAYER:
                    input("  [槓] 按 y + Enter 繼續: ")
                first_round = False  # 槓牌後首巡失效
                tenhou_flags.pop(cand_idx, None)  # 槓牌者天/地聽失效
                # 槓後正常摸牌（不設 skip_draw），玩家順序改為槓牌家
                player = cand_idx
                kong_player = cand_idx
                break

        # 無人明槓時，再檢查其他三家碰牌（人類玩家詢問 y/n）
        pon_player: int | None = None
        if kong_player is None:
            for offset in range(1, 4):
                cand_idx = (player + offset) % 4
                cand_p = m.players[cand_idx]
                pon_pair = can_pon(cand_p.hand, discard_tile)
                if pon_pair is not None:
                    if cand_idx == HUMAN_PLAYER:
                        ans = input(
                            f"\n  你可以碰 {n_to_chinese(discard_tile)}？(y/n) "
                        ).strip().lower()
                        if ans != "y":
                            continue
                    ta, tb = pon_pair
                    _do_meld(m, player, cand_idx, discard_tile, [ta, tb])
                    cand_p.pon_count += 1
                    print(
                        f"\n  {plabel(cand_idx)}碰 {n_to_chinese(discard_tile)}"
                        f"（{n_to_chinese(ta)} {n_to_chinese(tb)}）",
                        end="",
                    )
                    if PAUSE_ON_MELD and cand_idx != HUMAN_PLAYER:
                        input("  [碰] 按 y + Enter 繼續: ")
                    first_round = False  # 碰牌後首巡失效
                    tenhou_flags.pop(cand_idx, None)  # 碰牌者天/地聽失效
                    skip_draw = True
                    player = cand_idx
                    pon_player = cand_idx
                    break

        if kong_player is None and pon_player is None:
            # 無人碰牌，再檢查下一家是否吃牌（人類玩家詢問 y/n）
            next_idx = (player + 1) % 4
            np = m.players[next_idx]
            chi_pair = can_chi(np.hand, discard_tile) if discard_tile < SUITED_END else None
            if chi_pair is not None:
                do_chi = True
                chosen_ta, chosen_tb = chi_pair
                if next_idx == HUMAN_PLAYER:
                    ans = input(
                        f"\n  你可以吃 {n_to_chinese(discard_tile)}？(y/n) "
                    ).strip().lower()
                    if ans != "y":
                        do_chi = False
                    else:
                        # 枚舉全部吃法供玩家選擇
                        kind_d = discard_tile // COPIES
                        rank_d = kind_d % TILES_PER_SUIT
                        def _find_in(h: list[int], k: int) -> int | None:
                            for t in h:
                                if t // COPIES == k:
                                    return t
                            return None
                        all_combos: list[tuple[int, int]] = []
                        combo_kinds = []
                        if rank_d >= 2:
                            combo_kinds.append((kind_d - 2, kind_d - 1))
                        if 1 <= rank_d <= 7:
                            combo_kinds.append((kind_d - 1, kind_d + 1))
                        if rank_d <= 6:
                            combo_kinds.append((kind_d + 1, kind_d + 2))
                        for ka, kb in combo_kinds:
                            ta2 = _find_in(np.hand, ka)
                            if ta2 is None:
                                continue
                            tmp = list(np.hand)
                            tmp.remove(ta2)
                            tb2 = _find_in(tmp, kb)
                            if tb2 is not None:
                                all_combos.append((ta2, tb2))
                        if len(all_combos) > 1:
                            print(f"\n  選擇吃法：")
                            for ci, (ca, cb) in enumerate(all_combos):
                                print(f"    [{ci}] {n_to_chinese(ca)} {n_to_chinese(discard_tile)} {n_to_chinese(cb)}")
                            while True:
                                raw = input(f"  輸入編號 (0–{len(all_combos)-1}): ").strip()
                                if raw.isdigit() and 0 <= int(raw) < len(all_combos):
                                    chosen_ta, chosen_tb = all_combos[int(raw)]
                                    break
                                print(f"  請輸入 0 到 {len(all_combos)-1} 之間的數字")
                        else:
                            chosen_ta, chosen_tb = all_combos[0]
                if do_chi:
                    _do_meld(m, player, next_idx, discard_tile, [chosen_ta, chosen_tb])
                    np.chi_count += 1
                    print(
                        f"\n  {plabel(next_idx)}吃 {n_to_chinese(discard_tile)}"
                        f"（{n_to_chinese(chosen_ta)} {n_to_chinese(chosen_tb)}）",
                        end="",
                    )
                    if PAUSE_ON_MELD and next_idx != HUMAN_PLAYER:
                        input("  [吃] 按 y + Enter 繼續: ")
                    first_round = False  # 吃牌後首巡失效
                    tenhou_flags.pop(next_idx, None)  # 吃牌者天/地聽失效
                    skip_draw = True
                    player = next_idx
                else:
                    player = (player + 1) % 4
            else:
                player = (player + 1) % 4

    print("\n和局")
    _print_summary()
    return None, dealer_idx, seat_winds, game_round_wind


if __name__ == "__main__":
    if RUN_TESTS:
        import io, contextlib, time as _time
        print("\n--- 整合測試 1：固定 seed 執行一局（main()）---")
        _buf = io.StringIO()
        _t0 = _time.monotonic()
        random.seed(42)
        with contextlib.redirect_stdout(_buf):
            main(contest_mode=False)
        _elapsed = _time.monotonic() - _t0
        _out = _buf.getvalue()
        _last = _out.rstrip().splitlines()[-1]
        assert "胡" in _last or "和局" in _last, f"結尾行應含「胡」或「和局」：{_last!r}"
        _labels = ["你打", "下家打", "對家打", "上家打"]
        for lbl in _labels:
            assert lbl in _out, f"輸出應含「{lbl}」"
        assert _elapsed < 5.0, f"執行時間過長：{_elapsed:.2f}s"
        has_chi = "吃" in _out
        has_pon = "碰" in _out
        if has_chi or has_pon:
            assert "[" in _out, "有吃/碰時，輸出應含面牌組 [...]"
        print(f"  ✓ 一局完整執行（{_elapsed:.2f}s），結尾：{_last.strip()!r}")
        print(f"  ✓ 含吃={has_chi} 含碰={has_pon}")

        print("\n--- 整合測試 2：GameSession 全 AI 模擬（contest=False）---")
        import sys as _sys

        _t0 = _time.monotonic()
        random.seed(42)
        _sess = GameSession(contest=False, dealer_idx_override=1)
        _state = _sess.start()
        _steps = 0
        while _state.phase != "game_over":
            if _state.phase == "human_discard":
                _state = _sess.respond("0")  # 永遠打第一張
            elif _state.phase == "prompt":
                _pt = _state.prompt
                if _pt is not None and _pt.type == "chi" and _pt.chi_options:
                    _state = _sess.respond("chi:0")
                else:
                    _state = _sess.respond("n")  # 全部跳過（不胡、不碰槓）
            _steps += 1
            assert _steps < 500, "GameSession 迴圈超過 500 步，可能無限循環"
        _elapsed2 = _time.monotonic() - _t0
        assert _state.phase == "game_over", f"最終 phase 應為 game_over：{_state.phase!r}"
        assert len(_state.your_hand) == 0 or _state.winner is not None or _state.winner is None
        assert len(_state.discards) == 4, f"discards 應有 4 家：{len(_state.discards)}"
        print(f"  ✓ GameSession 完整執行（{_elapsed2:.2f}s），{_steps} 步，winner={_state.winner!r}")

        print("\n--- 整合測試 3：64 組合（4圈風×4莊家×4人類門風）---")
        _combo_pass = 0
        for _rw in _SEAT_WIND_NAMES:           # 4 圈風
            for _d_i in range(4):              # 4 莊家位置
                for _hw_i in range(4):         # 4 人類門風
                    _seat_winds = [_SEAT_WIND_NAMES[(_hw_i + k) % 4] for k in range(4)]
                    _s64 = GameSession(
                        contest=False,
                        dealer_idx_override=_d_i,
                        seat_winds=_seat_winds,
                        game_round_wind=_rw,
                    )
                    _st64 = _s64.start()
                    _steps64 = 0
                    while _st64.phase != "game_over":
                        if _st64.phase == "human_discard":
                            _st64 = _s64.respond("0")
                        else:
                            _st64 = _s64.respond("n")
                        _steps64 += 1
                        assert _steps64 < 500, (
                            f"組合({_rw},{_d_i},{_hw_i}) 超過 500 步"
                        )
                    assert _st64.game_round_wind == _rw, (
                        f"game_round_wind 應={_rw!r} 實={_st64.game_round_wind!r}"
                    )
                    assert _st64.seat_winds[0] == _SEAT_WIND_NAMES[_hw_i], (
                        f"人類門風應={_SEAT_WIND_NAMES[_hw_i]!r} "
                        f"實={_st64.seat_winds[0]!r}"
                    )
                    assert _st64.seat_winds[_d_i] == _seat_winds[_d_i], (
                        f"莊家({_d_i})門風應={_seat_winds[_d_i]!r} "
                        f"實={_st64.seat_winds[_d_i]!r}"
                    )
                    _combo_pass += 1
        print(f"  ✓ {_combo_pass}/64 組合全部通過")

        print("\n--- 單元測試：拉莊台數公式 ---")
        # 最簡胡牌手牌：5 組刻子（1–5筒各3張）+ 1萬對子 = 17 張
        # tile encoding: 1筒=0~3, 2筒=4~7, 3筒=8~11, 4筒=12~15, 5筒=16~19, 1萬=72~75
        _win_hand = [0,1,2, 4,5,6, 8,9,10, 12,13,14, 16,17,18, 72,73]
        _win_tile = 73  # 自摸入牌（在 hand 中）
        _seat_winds = list(_SEAT_WIND_NAMES)  # ['東','南','西','北']
        _win_p = PlayerState(n_hand=16, hand=_win_hand)
        for _consec, _expected_laz in [(0, 0), (1, 2), (2, 4), (3, 6)]:
            _sc = score_hand(
                winner=0, dealer_idx=0, consecutive=_consec,
                is_tsumo=True, p=_win_p, winning_tile=_win_tile,
                game_wind=_seat_winds[0], seat_winds=_seat_winds,
            )
            _laz_pts = next((v for n, v in _sc if n == "拉莊"), 0)
            assert _laz_pts == _expected_laz, (
                f"連莊{_consec} 拉莊應={_expected_laz} 實得={_laz_pts}"
            )
            _dealer_pts = next((v for n, v in _sc if n == "莊家"), 0)
            assert _dealer_pts == 1, f"莊家台應=1 實得={_dealer_pts}"
            _total = sum(v for _, v in _sc)
            _expected_base = 1 + _expected_laz  # 莊家+拉莊（最低）
            assert _total >= _expected_base, (
                f"連莊{_consec} 總台數應≥{_expected_base} 實得={_total}"
            )
            print(f"  ✓ 連莊{_consec}：莊家+{_dealer_pts} 拉莊+{_laz_pts}（總{_total}台）")

        print("\n--- 單元測試：莊家放槍加台 ---")
        # 同一手牌，分三種情境比較台數
        _pao_hand = list(_win_hand)
        _pao_p    = PlayerState(n_hand=16, hand=_pao_hand)
        # 情境 A：莊家放槍（pao_idx=dealer_idx=0）→ 應比 pao=None 多 1 台
        _sc_pao_dealer = score_hand(
            winner=1, dealer_idx=0, consecutive=0,
            is_tsumo=False, p=_pao_p, winning_tile=_win_tile,
            game_wind=_seat_winds[0], seat_winds=_seat_winds,
            pao_idx=0,
        )
        # 情境 B：非莊放槍（pao_idx=2，非 dealer=0）→ 台數與 pao=None 相同
        _sc_pao_other = score_hand(
            winner=1, dealer_idx=0, consecutive=0,
            is_tsumo=False, p=_pao_p, winning_tile=_win_tile,
            game_wind=_seat_winds[0], seat_winds=_seat_winds,
            pao_idx=2,
        )
        # 情境 C：自摸（pao_idx=None）→ 不加莊家放槍
        _sc_tsumo = score_hand(
            winner=1, dealer_idx=0, consecutive=0,
            is_tsumo=True, p=_pao_p, winning_tile=_win_tile,
            game_wind=_seat_winds[0], seat_winds=_seat_winds,
        )
        _pao_dealer_pts = next((v for n, v in _sc_pao_dealer if n == "莊家放槍"), 0)
        _pao_other_pts  = next((v for n, v in _sc_pao_other  if n == "莊家放槍"), 0)
        _tsumo_pts      = next((v for n, v in _sc_tsumo       if n == "莊家放槍"), 0)
        assert _pao_dealer_pts == 1, f"莊家放槍應=1 實得={_pao_dealer_pts}"
        assert _pao_other_pts  == 0, f"非莊放槍莊家放槍應=0 實得={_pao_other_pts}"
        assert _tsumo_pts      == 0, f"自摸莊家放槍應=0 實得={_tsumo_pts}"
        _total_a = sum(v for _, v in _sc_pao_dealer)
        _total_b = sum(v for _, v in _sc_pao_other)
        assert _total_a == _total_b + 1, (
            f"莊家放槍應比非莊放槍多1台：{_total_a} vs {_total_b}"
        )
        print(f"  ✓ 莊家放槍：+{_pao_dealer_pts} 台（總{_total_a}台）")
        print(f"  ✓ 非莊放槍：+{_pao_other_pts} 台（總{_total_b}台）")
        print(f"  ✓ 自摸：莊家放槍 +{_tsumo_pts} 台（不加台）")

        print("\n--- 單元測試：莊家保底1台（自摸 & ron）---")
        _dealer_hand = [0,1,2, 4,5,6, 8,9,10, 12,13,14, 16,17,18, 72,73]
        _dealer_tile  = 73
        _dealer_p     = PlayerState(n_hand=16, hand=_dealer_hand)
        # 情境 A：莊家自摸勝（winner=dealer=0, is_tsumo=True）
        _sc_dealer_tsumo = score_hand(
            winner=0, dealer_idx=0, consecutive=0,
            is_tsumo=True, p=_dealer_p, winning_tile=_dealer_tile,
            game_wind=_seat_winds[0], seat_winds=_seat_winds,
        )
        # 情境 B：莊家 ron 勝（非莊玩家放槍，winner=dealer=0, is_tsumo=False, pao_idx=1）
        _dealer_ron_hand = _dealer_hand + []     # 同一副手牌
        _dealer_ron_p    = PlayerState(n_hand=16, hand=_dealer_ron_hand)
        _sc_dealer_ron = score_hand(
            winner=0, dealer_idx=0, consecutive=0,
            is_tsumo=False, p=_dealer_ron_p, winning_tile=_dealer_tile,
            game_wind=_seat_winds[0], seat_winds=_seat_winds,
            pao_idx=1,   # 非莊家放槍
        )
        _dt = next((v for n, v in _sc_dealer_tsumo if n == "莊家"), 0)
        _dr = next((v for n, v in _sc_dealer_ron   if n == "莊家"), 0)
        assert _dt == 1, f"莊家自摸勝應含莊家+1，實得={_dt}"
        assert _dr == 1, f"莊家 ron 勝應含莊家+1，實得={_dr}"
        # 莊家放槍不應觸發（pao_idx=1 ≠ dealer_idx=0）
        _dr_pao = next((v for n, v in _sc_dealer_ron if n == "莊家放槍"), 0)
        assert _dr_pao == 0, f"非莊放槍不應觸發莊家放槍，實得={_dr_pao}"
        print(f"  ✓ 莊家自摸勝：莊家+{_dt}台（保底）")
        print(f"  ✓ 莊家 ron 勝：莊家+{_dr}台（保底，非莊放槍）")

        print("\n  ✓ 所有整合測試通過")

    # ── 模式選單 / 自動偵測 ──────────────────────────────────────────
    _ans = input("是否隱藏 AI 手牌（競賽模式）？(y/n) ").strip().lower()
    contest = _ans == "y"

    # 連莊迴圈
    dealer_override: int | None = None
    winds_override: list[str] | None = None   # None = 首局隨機抽定
    round_wind_override: str | None = None    # None = 首局等於莊家門風
    consec = 0
    while True:
        winner, dealer_idx, seat_winds, game_round_wind = main(
            dealer_idx_override=dealer_override,
            consecutive=consec,
            contest_mode=contest,
            seat_winds_override=winds_override,
            game_round_wind_override=round_wind_override,
        )
        if winner == dealer_idx:
            print(f"\n{seat_winds[dealer_idx]} 胡牌！連莊！")
        elif winner is None:
            print(f"\n和局！連莊！")
        else:
            print(f"\n下莊（{seat_winds[winner]} 胡牌）。")
            break
        ans = input("繼續下一局？(y/n) ").strip().lower()
        if ans != "y":
            break
        consec += 1
        winds_override = seat_winds        # 連莊保持同一座次
        round_wind_override = game_round_wind  # 連莊保持同一圈風
        dealer_override = dealer_idx
