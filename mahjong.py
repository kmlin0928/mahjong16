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
        table:    已亮出的花牌列表
        seen:     索引為牌面種類（tile // COPIES），記錄各牌面已出現張數
        discards: 該玩家本局打出的所有牌（依打出順序排列），供 AI 放槍預防使用
    """
    n_hand: int
    hand: list[int] = field(default_factory=list)
    table: list[int] = field(default_factory=list)
    seen: list[int] = field(default_factory=lambda: [0] * (SUITED_KINDS + HONOR_KINDS))
    discards: list[int] = field(default_factory=list)

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

    total = p.n_hand + 1        # 含摸入牌
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


def main() -> None:
    """四人 AI 麻將主遊戲迴圈。

    流程：
    1. 初始化並發牌、補花
    2. 四人輪流：摸牌 → 補花 → 判胡 → AI 計算 → 打牌 → 通知其他家記牌
    3. 胡牌或牌堆耗盡則結束
    """
    m = Mahjong(n_hand=16)
    m.init_deal()
    m.show_bonus()
    print()

    player = 0
    while m.remain:
        p = m.players[player]
        ai = m.ai[player]

        # 摸牌
        drawn = m.deal_one()
        print(f"\n{player}摸 {n_to_chinese(drawn)}", end="")
        p.hand.append(drawn)
        m._draw_bonus(p, len(p.hand) - 1)
        drawn = p.hand[-1]      # 補花後的實際摸入牌
        p.add_seen(drawn)

        # 判胡（摸牌後立即判斷）
        if is_win(p.hand[:-1], drawn):
            print(f"\n{player}胡", end="")
            for t in p.hand[:-1]:
                print(f" {n_to_chinese(t)}", end="")
            print()
            return

        # 牌堆若已空（補花後耗盡），宣告和局
        if not m.remain:
            break

        # AI 計算聽牌與出牌
        calculate_gates(m, p, ai)
        print(f" 打後聽牌:", end="")
        for gate_idx, chance in ai.gates.items():
            print(f" {n_to_chinese(p.hand[gate_idx])}={chance}", end="")

        # 決定出牌（傳入 players 啟用 DangerLevel 策略）
        discard_idx, discard_level = decide_play(p, ai, m.players)  # type: ignore[misc]
        # 將摸入牌換入打出位置（維持 hand 長度 = n_hand）
        discard_tile = p.hand[discard_idx]
        p.hand[discard_idx] = p.hand[-1]
        p.hand.pop()

        # 拆牌：被迫棄出 EXTREMELY_DANGEROUS 牌（湊牌）
        tear = "（拆牌）" if discard_level == DangerLevel.EXTREMELY_DANGEROUS else ""
        print(f"\n{player}打 {n_to_chinese(discard_tile)}{tear}_", end="")
        for t in p.hand:
            print(f" {n_to_chinese(t)}", end="")
        if p.table:
            for t in p.table:
                print(f"|{n_to_chinese(t)}", end="")

        # 棄牌記入該玩家個人棄牌紀錄，其他三家記牌
        p.discards.append(discard_tile)
        for other in range(1, 4):
            m.players[(player + other) % 4].add_seen(discard_tile)

        player = (player + 1) % 4

    print("\n和局")


if __name__ == "__main__":
    main()
