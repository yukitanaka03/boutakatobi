# services/weights.py — 外れにくさスコアの重み（要件定義書 6.2）
#
# 要素は7つ：好みに左右されにくさ・エピソードとの関連度・職場での渡しやすさ・送別での購入実績・評価・定番らしさ・個性。
#
# エピソードがあるとき：好みの把握度（low/mid/high）で重みを変える。どの把握度でも合計は 1.00。
#   - 好みを知らないほど「好みに左右されにくさ」と「定番らしさ」を重く見る
#   - 好みを知っているほど「エピソードとの関連度」を重く見て、よく知っているときだけ「個性」を足す（Bさん）
#   - mid は要件定義書に値が無いので、low と high のちょうど間に置いた
# エピソードがないとき：把握度に関係なく共通の重み。相手の好みの中身が入力されていないので、
#   個性的な商品を上に出す根拠が無い。関連度の分は「好みに左右されにくさ」と「定番らしさ」に重点的に配る
#   （機械的に配り直すと購入実績の比重が上がり、今のランキングに近づくため）。
# 配送のとき：職場で手渡ししないので、「職場での渡しやすさ」の重みを「好みに左右されにくさ」に足す。

KNOWLEDGE_LEVELS = ("low", "mid", "high")

WITH_EPISODE = {
    #       好みに左右されにくさ  エピソード      渡しやすさ        購入実績        評価            定番らしさ        個性
    "low":  {"preference": 0.30,  "episode": 0.25, "workplace": 0.10, "sales": 0.15, "rating": 0.10, "standard": 0.10, "unique": 0.0},
    "mid":  {"preference": 0.175, "episode": 0.35, "workplace": 0.10, "sales": 0.15, "rating": 0.10, "standard": 0.05, "unique": 0.075},
    "high": {"preference": 0.05,  "episode": 0.45, "workplace": 0.10, "sales": 0.15, "rating": 0.10, "standard": 0.0,  "unique": 0.15},
}
NO_EPISODE = {"preference": 0.35, "episode": 0.0, "workplace": 0.15, "sales": 0.20, "rating": 0.15, "standard": 0.15, "unique": 0.0}

# 互換のため（テストや他のファイルから WEIGHTS で参照している箇所向け）
WEIGHTS = WITH_EPISODE


def weights_for(knowledge: str, handover: str, has_episode: bool = False) -> dict:
    """把握度・渡し方・エピソードの有無から、その条件で使う重みを返す（合計 1.00）。"""
    if knowledge not in WITH_EPISODE:
        raise ValueError(f"preference_knowledge は {KNOWLEDGE_LEVELS} のどれか: {knowledge}")
    w = dict(WITH_EPISODE[knowledge] if has_episode else NO_EPISODE)
    if handover == "ship":
        w["preference"] += w["workplace"]
        w["workplace"] = 0.0
    return w
