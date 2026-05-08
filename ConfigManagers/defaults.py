from copy import deepcopy


APP_SETTINGS_DEFAULT = {
    "backup_settings": {
        "backup_base_path": {
            "value": "Backups",
            "description": "Percorso dove verranno salvati i backup del database gestionale.",
        },
        "interval_minutes": {
            "value": 25,
            "description": "Intervallo in minuti tra l'esecuzione dei backup.",
        },
        "max_backups": {
            "value": 15,
            "description": "Numero massimo di backup da conservare per ogni intervallo.",
        },
        "delta_days": {
            "value": 10,
            "description": "Intervallo di tempo in giorni tra le cartelle di backup.",
        },
        "backup_books_path": {
            "value": "",
            "description": "",
        },
    }
}


FISCAL_RULES_DEFAULT = {
    "fiscal_settings": {
        "iva": {
            "no_iva": {"value": "0.00", "description": "Assenza di IVA"},
            "aliquota_iva_ordinaria": {"value": "0.22", "description": "Aliquota IVA standard"},
            "aliquota_iva_ridotta_1": {
                "value": "0.10",
                "description": "Aliquota IVA ridotta per turismo, edilizia e servizi alimentari",
            },
            "aliquota_iva_ridotta_2": {
                "value": "0.05",
                "description": "Aliquota IVA ridotta per servizi sociali, sanitari ed educativi",
            },
            "aliquota_iva_minima": {
                "value": "0.04",
                "description": "Aliquota IVA ridotta per beni di prima necessita",
            },
        },
        "partita_iva_forfettaria": {
            "aliquota_irpef_min": {
                "value": "0.05",
                "description": "Aliquota IRPEF minima per partite IVA forfettarie, applicata nei primi anni.",
            },
            "aliquota_irpef_max": {
                "value": "0.15",
                "description": "Aliquota IRPEF massima per partite IVA forfettarie, applicata dopo il periodo agevolato.",
            },
            "anni_agevolazione": {
                "value": "5",
                "description": "Numero di anni durante i quali si applica la tariffa agevolata per il regime forfettario.",
            },
            "aliquota_inps": {
                "value": "0.2607",
                "description": "Contributo INPS per partite IVA forfettarie.",
            },
            "aliquota_rivalsa_inps": {
                "value": "0.04",
                "description": "Aliquota per rivalsa INPS in regime forfettario.",
            },
            "imponibile": {
                "value": "0.78",
                "description": "Percentuale dell'imponibile considerata per il calcolo fiscale nel regime forfettario.",
            },
            "percentuale_acconto_imposta_primo": {
                "value": "0.40",
                "description": "Quota (%) del primo acconto dell'imposta sostitutiva da versare al 30 giugno (saldo+acconto)",
            },
            "percentuale_acconto_imposta_secondo": {
                "value": "0.60",
                "description": "Quota (%) del secondo acconto dell'imposta sostitutiva da versare al 30 novembre",
            },
            "percentuale_acconto_inps_forfettario": {
                "value": "1.00",
                "description": "Percentuale dei contributi INPS forfettari su cui calcolare gli acconti (sempre 100% del contributo dovuto)",
            },
            "percentuale_rata_acconto_inps_forfettario": {
                "value": "0.50",
                "description": "Quota (%) di ciascuna delle due rate di acconto INPS (30 giugno e 30 novembre) in regime forfettario",
            },
        },
        "partita_iva_ordinaria": {
            "aliquota_irpef_1": {
                "value": "0.23",
                "reddito_min": "0.0",
                "reddito_max": "28000",
                "description": "Aliquota IRPEF per il primo scaglione di reddito.",
            },
            "aliquota_irpef_2": {
                "value": "0.35",
                "reddito_min": "28000",
                "reddito_max": "50000",
                "description": "Aliquota IRPEF per il secondo scaglione di reddito",
            },
            "aliquota_irpef_3": {
                "value": "0.43",
                "reddito_min": "50000",
                "reddito_max": "+Infinity",
                "description": "Aliquota IRPEF per il terzo scaglione di reddito",
            },
            "aliquota_inps": {
                "value": "0.2607",
                "description": "Contributo INPS per partite IVA ordinarie",
            },
            "aliquota_cassa_inps": {"value": "0.04", "description": "Aliquota per la cassa INPS"},
            "aliquota_ritenuta": {"value": "0.2", "description": "Aliquota per la ritenuta d'acconto"},
            "imponibile_iva": {"value": "1", "description": "Coefficiente per il calcolo dell'imponibile IVA"},
            "imponibile_ritenuta_acconto": {
                "value": "1",
                "description": "Coefficiente per il calcolo dell'imponibile per la ritenuta d'acconto",
            },
            "imponibile_cassa_inps": {
                "value": "1",
                "description": "Coefficiente per il calcolo dell'imponibile per la cassa INPS",
            },
            "imponibile_inps": {"value": "1", "description": "Coefficiente per il calcolo dell'imponibile per l'INPS"},
            "imponibile_irpef": {
                "value": "1",
                "description": "Coefficiente per il calcolo dell'imponibile per l'IRPEF",
            },
            "percentuale_acconto_irpef_primo": {
                "value": "0.40",
                "description": "Quota (%) del primo acconto IRPEF da versare a saldo+acconto al 30 giugno",
            },
            "percentuale_acconto_irpef_secondo": {
                "value": "0.60",
                "description": "Quota (%) del secondo acconto IRPEF da versare al 30 novembre",
            },
            "percentuale_acconto_inps": {
                "value": "0.80",
                "description": "Percentuale degli ultimi contributi INPS su cui calcolare gli acconti per l'anno in corso",
            },
            "percentuale_rata_acconto_inps": {
                "value": "0.50",
                "description": "Quota (%) di ciascuna delle due rate di acconto INPS (30 giugno e 30 novembre)",
            },
        },
    }
}


CATALOGS_DEFAULT = {
    "clients_business_sectors": {
        "AEROSPACE": "Aerospaziale e Difesa",
        "AGRICULTURE": "Agricoltura e Allevamento",
        "CREATIVE_AGENCY": "Agenzia Creativa",
        "FOOD_AND_BEVERAGE": "Alimentare e Bevande",
        "AUTOMOTIVE": "Automobilistico",
        "CHEMICAL": "Chimico",
        "RETAIL": "Commercio al Dettaglio",
        "WHOLESALE": "Commercio all'Ingrosso",
        "CONSULTING": "Consulenza e Servizi Professionali",
        "CONSTRUCTION": "Costruzioni e Edilizia",
        "ENERGY": "Energia e Risorse Naturali",
        "PHARMACEUTICAL": "Farmaceutico",
        "FINANCE": "Finanza e Assicurazioni",
        "GOVERNMENT": "Governo e Settore Pubblico",
        "REAL_ESTATE": "Immobiliare",
        "EDUCATION": "Istruzione e Formazione",
        "ENTERTAINMENT": "Intrattenimento e Media",
        "MANUFACTURING": "Manifatturiero e Produzione",
        "NON_PROFIT": "Organizzazioni Non Profit",
        "RESEARCH_AND_DEVELOPMENT": "Ricerca e Sviluppo",
        "HEALTHCARE": "Sanita e Servizi Medici",
        "ENVIRONMENTAL_SERVICES": "Servizi Ambientali",
        "SECURITY": "Sicurezza e Vigilanza",
        "SPORTS": "Sport e Benessere",
        "INFORMATION_TECHNOLOGY": "Tecnologia dell'Informazione (IT)",
        "TELECOMMUNICATIONS": "Telecomunicazioni",
        "TEXTILE": "Tessile e Abbigliamento",
        "TOURISM": "Turismo e Ospitalita",
        "TRANSPORTATION": "Trasporti e Logistica",
        "ADD_SECTOR": "AGGIUNGI UN SETTORE ALLA LISTA",
    },
    "production_types": {
        "PRODUZIONE": "Produzione",
        "POST_PRODUZIONE": "Postproduzione",
        "MISTA": "Mista",
        "CONSULENZA": "Consulenza",
        "ADD_PROD_TYPE": "AGGIUNGI UNA TIPOLOGIA ALLA LISTA",
    },
    "production_output_types": {
        "VIDEO_MUSICALE": "Video musicale",
        "ADV_SOCIAL": "ADV social",
        "COMMERCIAL": "Commercial",
        "INTEGRAZIONE_VFX": "Integrazione VFX",
        "ADD_PROD_OUT_TYPE": "AGGIUNGI UNA TIPOLOGIA DI OUTPUT ALLA LISTA",
    },
    "expenses_category": {
        "MANUTENZIONE": "manutenzione",
        "SPONSORIZZAZIONE": "sponsorizzazione",
        "TASSE": "tasse",
        "STUDIO_RENTAL": "Affitto Ufficio",
        "TECHNICAL_INSTRUMENTATION_PROD": "Strumentazione tecnica produzione",
        "TECHNICAL_INSTRUMENTATION_POSTPROD": "Strumentazione tecnica postproduzione",
        "SUBSCRIPTION": "Abbonamento",
        "ELECTRICITY_BILL": "Bolletta Luce",
        "GAS_BILL": "Bolletta Gas",
        "INTERNET_BILL": "Abbonamento Internet",
        "WASTE_BILL": "TARI",
        "CONSUMABLE_FOR_STUDIO": "Consumabili per lo studio",
        "INSURANCE": "Assicurazionee",
        "PRODUCTION_EXPENSE": "Spesa di produzione",
        "USER_SALARY": "Salario",
        "TRIMESTRAL_IVA": "Iva trimestrale",
        "ADD_CATEGORY": "AGGIUNGI UNA CATEGORIA ALLA LISTA"
    },
}


RECURRING_EXPENSES_DEFAULT = {"recurring_expenses": {}}


HISTORICAL_FINANCIAL_DATA_DEFAULT = {
    "revenues": {},
    "deducted_expenses": {},
}


def clone_default_config(default_config):
    return deepcopy(default_config)
