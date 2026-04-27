"""
Nelson-Siegel Web Application

A Flask-based web interface for exploring Nelson-Siegel yield curve models.
Provides curve fitting, parameter exploration, historical analysis, and
Treasury vs TIPS comparison through an interactive browser UI.
"""

from .app import create_app, run_app

__all__ = ["create_app", "run_app"]
