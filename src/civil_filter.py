import re

HEAD_N = 3500  # title + bench + headnotes

CORE = {
    "transfer_of_property": r"transfer of property act",
    "specific_relief": r"specific relief act|specific performance",
    "contract": r"indian contract act|sale of goods act|breach of contract",
    "easements": r"\beasements?\b",
    "partition_title": r"\bpartition\b|declaration of title|suit for possession|adverse possession",
    "succession": r"succession act|\bprobate\b|testamentary",
    "mortgage": r"\bmortgage\b|\bredemption\b",
    "civil_procedure": r"res judicata|temporary injunction|permanent injunction|execution of (?:the )?decree|decree[- ]holder",
    "tenancy": r"rent control|\btenan(?:t|ts|cy)\b|\blandlords?\b|\beviction\b",
}
SOFT = {
    "cpc": r"code of civil procedure|\bc\.?p\.?c\.?\b",
    "civil_suit": r"\bplaintiffs?\b|\bsuit\b|\bsale deed\b|agreement (?:to|for) sell|agreement for sale|title suit",
}
WEAK = {
    "lease": r"\bleases?\b|\bleasehold\b",
    "limitation": r"limitation act|barred by limitation|period of limitation",
    "registration": r"registration act|unregistered",
}
NEG = re.compile(
    r"land acquisition|acquisition proceedings|income[- ]tax|central excise|service tax"
    r"|customs act|employee.?s compensation|eco-sensitive",
    re.I,
)

C_RE = {k: re.compile(v, re.I) for k, v in CORE.items()}
S_RE = {k: re.compile(v, re.I) for k, v in SOFT.items()}
W_RE = {k: re.compile(v, re.I) for k, v in WEAK.items()}


def classify(text, forum):
    head = text[:HEAD_N]
    core = [k for k, rx in C_RE.items() if rx.search(head)]
    soft = [k for k, rx in S_RE.items() if rx.search(head)]
    weak = [k for k, rx in W_RE.items() if rx.search(head)]
    neg = bool(NEG.search(head))
    score = 2 * len(core) + 1 * len(soft) + 0.5 * len(weak)
    flag = (forum != "criminal") and score >= 2 and (len(core) >= 1 or not neg)
    return {"core": core, "soft": soft, "weak": weak, "neg": neg,
            "score": score, "civil_flag": flag}
