#!/usr/bin/env python3
"""
Moteur Python de pronostic Quinté+.

Entrée: JSON avec une clé "horses" contenant les partants.
Sortie: classement, probabilités top5, value bets et tickets conseillés.

Le moteur reste volontairement sans dépendance externe pour fonctionner sur PC,
serveur, Android/Termux ou GitHub Actions.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


DEFAULT_WEIGHTS = {
    "presse": 0.18,
    "forme": 0.18,
    "terrain": 0.11,
    "musique": 0.14,
    "cote": 0.11,
    "driver": 0.08,
    "consensus": 0.10,
    "meteo": 0.05,
    "technique": 0.05,
}

DISCIPLINE_ADJUSTMENTS = {
    "trot": {"driver": 0.04, "musique": 0.03, "terrain": -0.03, "cote": -0.01},
    "plat": {"terrain": 0.03, "cote": 0.02, "driver": -0.01, "musique": -0.02},
    "obstacle": {"forme": 0.03, "terrain": 0.04, "musique": 0.02, "cote": -0.03},
}


@dataclass
class Horse:
    num: int
    nom: str
    raw: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    prob: float = 0.0
    fair_odds: float = 0.0
    value_ratio: float | None = None
    components: Dict[str, float] = field(default_factory=dict)


def clamp(value: Any, low: float = 0.0, high: float = 10.0, default: float = 5.0) -> float:
    try:
        x = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(x):
        return default
    return max(low, min(high, x))


def odds_to_decimal(value: Any) -> float | None:
    if value in (None, "", "?"):
        return None
    text = str(value).strip().replace(",", ".")
    frac = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)
    if frac:
        a, b = float(frac.group(1)), float(frac.group(2))
        return a / b if b else None
    num = re.search(r"\d+(?:\.\d+)?", text)
    return float(num.group(0)) if num else None


def musique_score(musique: Any) -> float:
    text = str(musique or "").strip()
    if not text or text == "?":
        return 5.0
    tokens = re.findall(r"(\d+|Da|Dai|D|A|T|R)", text, flags=re.I)
    if not tokens:
        return 5.0
    total = 0.0
    weight_sum = 0.0
    weight = 1.0
    for token in tokens[:8]:
        if token[0].isdigit():
            pos = int(token)
            value = max(0.0, 11.0 - min(pos, 12))
        else:
            value = 1.0
        total += value * weight
        weight_sum += weight
        weight *= 0.86
    return total / weight_sum if weight_sum else 5.0


def text_signal_score(text: Any) -> float:
    s = str(text or "").lower()
    if not s or s == "?":
        return 5.0
    score = 5.0
    positives = ["base", "favori", "cité", "cite", "confiance", "régulier", "regulier", "bonne chance", "tocard"]
    negatives = ["risque", "décevant", "decevant", "rentrée", "rentree", "absent", "baisse", "fautif", "np"]
    score += sum(0.7 for p in positives if p in s)
    score -= sum(0.8 for n in negatives if n in s)
    cited = re.search(r"(\d+)\s*(?:sources|cit)", s)
    if cited:
        score += min(2.0, int(cited.group(1)) * 0.35)
    avg = re.search(r"rang moyen\s*(\d+(?:[.,]\d+)?)", s)
    if avg:
        score += max(-2.0, 2.0 - float(avg.group(1).replace(",", ".")) / 2.5)
    return clamp(score)


def normalize_weights(course: Dict[str, Any]) -> Dict[str, float]:
    weights = DEFAULT_WEIGHTS.copy()
    discipline = str(course.get("discipline", "")).lower()
    for key, delta_map in DISCIPLINE_ADJUSTMENTS.items():
        if key in discipline:
            for k, delta in delta_map.items():
                weights[k] = max(0.01, weights[k] + delta)
    if "handicap" in str(course.get("prix", "")).lower():
        weights["cote"] += 0.03
        weights["presse"] = max(0.01, weights["presse"] - 0.03)
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def build_horses(data: Dict[str, Any]) -> List[Horse]:
    rows = data.get("horses") or data.get("partants") or []
    horses: List[Horse] = []
    for row in rows:
        if row.get("np"):
            continue
        try:
            num = int(row.get("num"))
        except (TypeError, ValueError):
            continue
        horses.append(Horse(num=num, nom=str(row.get("nom") or row.get("name") or f"N°{num}"), raw=row))
    return sorted(horses, key=lambda h: h.num)


def score_horses(horses: List[Horse], course: Dict[str, Any]) -> None:
    weights = normalize_weights(course)
    odds_values = [odds_to_decimal(h.raw.get("cote") or h.raw.get("odds")) for h in horses]
    valid_odds = [x for x in odds_values if x and x > 0]
    min_odds = min(valid_odds) if valid_odds else 1.0
    max_odds = max(valid_odds) if valid_odds else 30.0

    for h in horses:
        odds = odds_to_decimal(h.raw.get("cote") or h.raw.get("odds") or h.raw.get("cote_num"))
        cote_score = 5.0
        if odds and max_odds > min_odds:
            cote_score = (max_odds - odds) / (max_odds - min_odds) * 10.0

        driver_text = " ".join(str(h.raw.get(k, "")) for k in ("driver_stats", "driver", "jockey"))
        driver_match = re.search(r"(\d+)\s*%", driver_text)
        driver_score = clamp(float(driver_match.group(1)) / 3.0 if driver_match else 5.0)

        risk_text = " ".join(str(h.raw.get(k, "")) for k in ("risque", "techRisque", "forme_tendance", "contexte"))
        risk_penalty = 1.0
        if re.search(r"fort|baisse|fautif|rentrée|rentree|décevant|decevant", risk_text, re.I):
            risk_penalty *= 0.94
        if re.search(r"hausse|progress|régulier|regulier|base", risk_text, re.I):
            risk_penalty *= 1.04

        components = {
            "presse": clamp(h.raw.get("presse") or h.raw.get("pts")),
            "forme": clamp(h.raw.get("forme") or h.raw.get("fo")),
            "terrain": clamp(h.raw.get("terrain") or h.raw.get("te")),
            "musique": musique_score(h.raw.get("musique")),
            "cote": clamp(cote_score),
            "driver": driver_score,
            "consensus": text_signal_score(h.raw.get("consensus") or h.raw.get("consensus_presse")),
            "meteo": clamp(h.raw.get("meteo_avantage") or h.raw.get("meteo_av")),
            "technique": clamp(h.raw.get("techS") or h.raw.get("technique")),
        }
        h.components = components
        h.score = sum(components[k] * weights[k] for k in weights) * risk_penalty

    total = sum(max(0.01, h.score) for h in horses) or 1.0
    for h in horses:
        h.prob = max(0.01, h.score) / total
        h.fair_odds = 1.0 / h.prob if h.prob else 999.0
        odds = odds_to_decimal(h.raw.get("cote") or h.raw.get("odds") or h.raw.get("cote_num"))
        h.value_ratio = odds / h.fair_odds if odds and h.fair_odds else None


def weighted_order(horses: Sequence[Horse], rng: random.Random) -> List[Horse]:
    remaining = list(horses)
    order: List[Horse] = []
    while remaining:
        total = sum(max(0.001, h.score) ** 1.35 for h in remaining)
        pick = rng.random() * total
        acc = 0.0
        for idx, horse in enumerate(remaining):
            acc += max(0.001, horse.score) ** 1.35
            if acc >= pick:
                order.append(horse)
                remaining.pop(idx)
                break
    return order


def simulate(horses: List[Horse], runs: int, seed: int) -> Dict[int, Dict[str, float]]:
    rng = random.Random(seed)
    stats = {h.num: {"win": 0, "top3": 0, "top5": 0, "score": 0.0} for h in horses}
    for _ in range(runs):
        order = weighted_order(horses, rng)
        for pos, horse in enumerate(order[:5], start=1):
            if pos == 1:
                stats[horse.num]["win"] += 1
            if pos <= 3:
                stats[horse.num]["top3"] += 1
            stats[horse.num]["top5"] += 1
            stats[horse.num]["score"] += 6 - pos
    for h in horses:
        s = stats[h.num]
        for key in ("win", "top3", "top5"):
            s[key] /= runs
        s["sim_score"] = s.pop("score") / runs
    return stats


def best_combinations(ranked: List[Horse], stats: Dict[int, Dict[str, float]]) -> Dict[str, Any]:
    pool = ranked[:8]

    def combo_score(nums: Tuple[int, ...]) -> float:
        return sum(stats[n]["top5"] for n in nums) + sum((1.0 / (i + 1)) for i, n in enumerate(nums) if n in [h.num for h in ranked[:5]])

    quinte_desordre = max(itertools.combinations([h.num for h in pool], 5), key=combo_score)
    quarte_desordre = max(itertools.combinations([h.num for h in pool[:7]], 4), key=combo_score)
    tierce_desordre = max(itertools.combinations([h.num for h in pool[:6]], 3), key=combo_score)
    ordre = [h.num for h in ranked[:5]]
    outsider = next((h.num for h in ranked[5:10] if (h.value_ratio or 0) >= 1.15), ranked[min(5, len(ranked) - 1)].num)

    return {
        "quinte_ordre": ordre,
        "quinte_desordre": list(quinte_desordre),
        "quinte_champ_reduit_7": [h.num for h in ranked[:7]],
        "quarte_desordre": list(quarte_desordre),
        "tierce_desordre": list(tierce_desordre),
        "base": ranked[0].num,
        "bases": [h.num for h in ranked[:2]],
        "tocard_value": outsider,
    }


def explain_horse(h: Horse, sim: Dict[str, float]) -> str:
    best = sorted(h.components.items(), key=lambda kv: kv[1], reverse=True)[:3]
    value = f"value x{h.value_ratio:.2f}" if h.value_ratio else "value inconnue"
    return (
        f"N°{h.num} {h.nom}: score {h.score:.2f}, top5 {sim['top5']*100:.1f}%, "
        f"gagnant {sim['win']*100:.1f}%, {value}, forces "
        + ", ".join(f"{k}={v:.1f}" for k, v in best)
    )


def run_engine(data: Dict[str, Any], runs: int, seed: int) -> Dict[str, Any]:
    course = data.get("course") or {}
    horses = build_horses(data)
    if len(horses) < 5:
        raise SystemExit("Il faut au moins 5 partants valides.")
    score_horses(horses, course)
    sim = simulate(horses, runs=runs, seed=seed)
    ranked = sorted(horses, key=lambda h: (sim[h.num]["top5"], h.score), reverse=True)
    tickets = best_combinations(ranked, sim)
    return {
        "course": course,
        "runs": runs,
        "ranking": [
            {
                "rank": i + 1,
                "num": h.num,
                "nom": h.nom,
                "score": round(h.score, 4),
                "prob_base": round(h.prob, 5),
                "fair_odds": round(h.fair_odds, 2),
                "value_ratio": round(h.value_ratio, 3) if h.value_ratio else None,
                "win": round(sim[h.num]["win"], 5),
                "top3": round(sim[h.num]["top3"], 5),
                "top5": round(sim[h.num]["top5"], 5),
                "components": {k: round(v, 3) for k, v in h.components.items()},
                "explain": explain_horse(h, sim[h.num]),
            }
            for i, h in enumerate(ranked)
        ],
        "tickets": tickets,
        "value_bets": [
            {"num": h.num, "nom": h.nom, "value_ratio": round(h.value_ratio, 3)}
            for h in ranked
            if h.value_ratio and h.value_ratio >= 1.12
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Moteur Python Quinté+")
    parser.add_argument("input", type=Path, help="Fichier JSON contenant course + horses/partants")
    parser.add_argument("--runs", type=int, default=50000, help="Nombre de simulations")
    parser.add_argument("--seed", type=int, default=42, help="Seed aléatoire")
    parser.add_argument("--pretty", action="store_true", help="Affichage lisible")
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = run_engine(data, runs=args.runs, seed=args.seed)
    if args.pretty:
        print("CLASSEMENT")
        for row in result["ranking"][:10]:
            print(f"{row['rank']:>2}. N°{row['num']} {row['nom']} | top5 {row['top5']*100:.1f}% | score {row['score']:.2f}")
        print("\nTICKETS")
        for key, value in result["tickets"].items():
            print(f"{key}: {value}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
