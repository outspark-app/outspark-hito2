"""Valores de dominio; sin framework ni SDK."""

import re


class RuleViolation(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise RuleViolation("invalid_identifier", "Identificador inválido")
    return value


def content(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 1000:
        raise RuleViolation("invalid_text", "Texto de 1 a 1000 caracteres.")
    return value.strip()


def topic_ids(values, minimum=0):
    if not isinstance(values, list) or not minimum <= len(values) <= 3:
        raise RuleViolation("invalid_topics", "Se admiten hasta tres temas distintos.")
    for value in values:
        identifier(value)
    if len(set(values)) != len(values):
        raise RuleViolation("invalid_topics", "Temas repetidos.")
    return sorted(values)
