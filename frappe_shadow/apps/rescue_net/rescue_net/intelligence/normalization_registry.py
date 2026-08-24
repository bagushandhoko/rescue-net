import re

import frappe

from rescue_net.intelligence.normalization import (
    classify_text as builtin_classify_text,
)


def _normalize(value):
    value = (value or "").casefold()
    value = re.sub(r"[^\w]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _aliases(value):
    return [
        _normalize(x)
        for x in (value or "").splitlines()
        if _normalize(x)
    ]


def _matches(text, alias, mode):
    if not text or not alias:
        return False

    if mode == "exact":
        return text == alias

    # Word/phrase aware contains match.
    return (
        f" {alias} "
        in f" {text} "
    )


def _configured_match(raw):
    if not frappe.db.exists(
        "DocType",
        "RN Normalization Rule",
    ):
        return None

    text = _normalize(raw)

    if not text:
        return None

    rules = frappe.get_all(
        "RN Normalization Rule",
        filters={"enabled": 1},
        fields=[
            "name",
            "priority",
            "canonical_category",
            "canonical_group",
            "canonical_item",
            "match_mode",
            "aliases",
            "confidence",
        ],
        order_by="priority desc, modified desc",
        limit_page_length=2000,
    )

    winner = None

    for rule in rules:
        for alias in _aliases(rule.aliases):
            if not _matches(
                text,
                alias,
                rule.match_mode or "contains",
            ):
                continue

            score = (
                int(rule.priority or 0),
                len(alias),
            )

            if (
                winner is None
                or score > winner["score"]
            ):
                winner = {
                    "score": score,
                    "rule": rule,
                    "alias": alias,
                }

    return winner


def classify_text(raw):
    # Preserve quantity parsing and existing fallback rules.
    result = dict(
        builtin_classify_text(raw)
    )

    winner = _configured_match(raw)

    if not winner:
        return result

    rule = winner["rule"]

    result["canonical_category"] = (
        rule.canonical_category
    )
    result["canonical_group"] = (
        rule.canonical_group
    )

    if rule.canonical_item:
        result["canonical_item"] = (
            rule.canonical_item
        )

    result["normalization_source"] = "rule"
    result["normalization_confidence"] = int(
        rule.confidence or 95
    )
    result["normalization_rule"] = rule.name
    result["matched_alias"] = winner["alias"]

    return result
