from Views.Adders.Base_catalog_item_adder_view import BaseCatalogItemAdderView


class ProductionOutputTypeAdderView(BaseCatalogItemAdderView):
    """Modale dedicata all'aggiunta di una nuova tipologia di output."""

    SECTION_NAME = "production_output_types"
    TITLE = "Aggiungi una nuova tipologia di output"
    DESCRIPTION = "Aggiungi una nuova tipologia di output di produzione\nsepara parole diverse solo tramite spazio"
    BUTTON_TEXT = "Aggiungi tipologia di output"
