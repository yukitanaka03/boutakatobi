# services/weights.py — 外れにくさスコアの重み（要件定義書 6.2）
#
# 好みの把握度（preference_knowledge）ごとに、6つの要素の重みを決める。どの把握度でも合計は 1.00。
#   - 好みを知らないほど「好みに左右されにくさ」を重く見る（Aさん：香り・甘さで1位2位を見送った）
#   - 好みを知っているほど「エピソードとの関連度」と「個性的か」を重く見る（Bさん：人気1位は普通すぎる）
#   - mid（少し知っている）は low と high のちょうど間に置いた（要件定義書には値が無いので、班で仮置き）
# エピソード関連度（FR-5）は来週実装。今週はテーマが渡されないので、値は 0 になる（重みは残す）。

KNOWLEDGE_LEVELS = ("low", "mid", "high")

WEIGHTS = {
    #               好みに左右されにくさ  エピソード  職場での渡しやすさ  送別での購入実績  評価   無難さ／個性
    "low":  {"preference": 0.30,  "episode": 0.25,  "workplace": 0.15,  "sales": 0.15,  "rating": 0.10, "style": 0.05},
    "mid":  {"preference": 0.175, "episode": 0.325, "workplace": 0.125, "sales": 0.15,  "rating": 0.10, "style": 0.125},
    "high": {"preference": 0.05,  "episode": 0.40,  "workplace": 0.10,  "sales": 0.15,  "rating": 0.10, "style": 0.20},
}


def weights_for(knowledge: str, handover: str) -> dict:
    """把握度と渡し方から、その条件で使う重みを返す。

    配送（ship）のときは職場で手渡ししないので、「職場での渡しやすさ」の重みを 0 にする（要件定義書 6.2）。
    その分は配り直さない。合計が 1 未満になっても、同じ条件の中での順位は変わらないため。
    """
    if knowledge not in WEIGHTS:
        raise ValueError(f"preference_knowledge は {KNOWLEDGE_LEVELS} のどれか: {knowledge}")
    w = dict(WEIGHTS[knowledge])
    if handover == "ship":
        w["workplace"] = 0.0
    return w
