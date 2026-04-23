from Views.Adders.Base_catalog_item_adder_view import BaseCatalogItemAdderView


class BusinessSectorAdderView(BaseCatalogItemAdderView):
    """Modale dedicata all'aggiunta di un nuovo settore di business."""

    SECTION_NAME = "clients_business_sectors"
    TITLE = "Aggiungi Nuovo Settore"
    DESCRIPTION = "Inserisci un nuovo settore di business"
    BUTTON_TEXT = "Aggiungi settore"
