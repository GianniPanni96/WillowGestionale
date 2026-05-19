"""
Modulo di retrocompatibilita': l'ex ``WarningsVisibilityManager`` e'
stato riassorbito in ``GuiPreferencesManager`` (gestore di tutte le
preferenze GUI in ``gui_preferences.json``). Re-export per non rompere
eventuali import legacy.
"""

from ConfigManagers.gui_preferences_manager import GuiPreferencesManager

WarningsVisibilityManager = GuiPreferencesManager

__all__ = ["WarningsVisibilityManager"]
