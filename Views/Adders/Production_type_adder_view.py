from Views.Adders.Base_catalog_item_adder_view import BaseCatalogItemAdderView


class ProductionTypeAdderView(BaseCatalogItemAdderView):
    """Modale dedicata all'aggiunta di una nuova tipologia di produzione."""

    SECTION_NAME = "production_types"
    TITLE = "Aggiungi una nuova tipologia di produzione"
    DESCRIPTION = "Aggiungi una nuova tipologia di produzione\nsepara parole diverse solo tramite spazio"
    BUTTON_TEXT = "Aggiungi tipologia produzione"
