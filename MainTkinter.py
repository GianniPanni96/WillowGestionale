"""
Entry-point della UI legacy customtkinter.

Esegue il bootstrap condiviso (config + AppContext + backup scheduler) e
avvia la MainWindow Tkinter. Mantenuta in parallelo a MainQT.py finche'
il porting verso Qt non sara' completato.
"""

from Main_bootstrap import build_app_context


def main():
    app_context, scheduler = build_app_context()

    from Views.View import MainWindow

    app = MainWindow(app_context)

    def on_closing():
        print("Finestra chiusa: arresto scheduler backup…")

        # Pulisce i timer dovuti al lazy loading delle tab.
        if hasattr(app, "_cancel_all_after"):
            app._cancel_all_after()

        scheduler.stop()
        app.quit()
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_closing)

    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("Interruzione manuale. Fermando il backup...")
        scheduler.stop()
        raise


if __name__ == "__main__":
    main()
