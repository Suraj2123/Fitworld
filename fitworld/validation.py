"""Shared server-side validation; never trust the browser's form constraints."""

import math
import re


class ValidationError(Exception):
    def __init__(self, fields):
        self.fields = fields


class Form:
    def __init__(self, data):
        self.data = data
        self.errors = {}

    def text(self, key, label, maximum, minimum=1, strip=True):
        value = self.data.get(key)
        if isinstance(value, str):
            value = value.strip() if strip else value
        if not isinstance(value, str) or not minimum <= len(value) <= maximum:
            self.errors[key] = f"{label} must contain {minimum}–{maximum} characters."
            return ""
        return value

    def number(self, key, label, minimum, maximum, integer=False):
        raw = self.data.get(key)
        try:
            if isinstance(raw, bool) or raw is None:
                raise ValueError
            value = float(raw)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError
            if integer and not value.is_integer():
                raise ValueError
            return int(value) if integer else value
        except (TypeError, ValueError, OverflowError):
            whole = "whole " if integer else ""
            self.errors[key] = f"Enter a {whole}number from {minimum} to {maximum} for {label}."
            return None

    def choice(self, key, options, label):
        value = self.data.get(key)
        if not isinstance(value, str) or value not in options:
            self.errors[key] = f"Choose {label}."
            return None
        return value

    def finish(self):
        if self.errors:
            raise ValidationError(self.errors)


def account(data, registering=True):
    form = Form(data)
    email = form.text("email", "Email", 254).lower()
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        form.errors["email"] = "Enter a valid email address."
    password = form.text("password", "Password", 128, 8 if registering else 1, strip=False)
    name = form.text("display_name", "Name", 80) if registering else None
    form.finish()
    return email, password, name


def body_weight(form):
    """Common body-weight bounds and conversion for onboarding and later check-ins."""
    unit = form.choice("unit_system", {"metric", "imperial"}, "your weight unit")
    minimum, maximum = (44.1, 881.8) if unit == "imperial" else (20, 400)
    weight = form.number("weight", "weight", minimum, maximum)
    if weight is None:
        return None, unit
    kg = weight * 0.45359237 if unit == "imperial" else weight
    return min(400, max(20, round(kg, 3))), unit


def profile(data):
    form = Form(data)
    age = form.number("age", "age", 13, 120, integer=True)
    kg, unit = body_weight(form)
    experience = form.choice("experience_level", {"beginner", "intermediate", "advanced"}, "your experience level")
    current = form.number("current_workouts_per_week", "current weekly workouts", 0, 7, integer=True)
    form.finish()
    return age, kg, unit, experience, current


def preferences(data):
    form = Form(data)
    goal = form.choice("primary_goal", {"get_active", "build_strength", "improve_endurance", "improve_mobility"}, "a goal")
    location = form.choice("training_location", {"home", "gym", "outdoors"}, "a workout location")
    days = form.number("target_days_per_week", "weekly workout days", 1, 7, integer=True)
    minutes = form.number("session_minutes", "session length", 15, 90, integer=True)
    if minutes is not None and minutes not in {15, 30, 45, 60, 90}:
        form.errors["session_minutes"] = "Choose 15, 30, 45, 60, or 90 minutes."
    form.finish()
    return goal, location, days, minutes
