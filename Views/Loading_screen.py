import threading
import cv2
import tkinter as tk
from PIL import Image, ImageTk
import time
from typing import Optional, List


class LoadingScreen:
    def __init__(
            self,
            media_path: str,
            window_title: str = "Caricamento...",
            width: Optional[int] = None,
            height: Optional[int] = None,
            loop: bool = True,
            transparency: float = 1.0
    ):
        """
        Inizializza la schermata di caricamento.

        Args:
            media_path: Percorso del video o immagine (supporta .mp4, .avi, .png, .gif, etc.)
            window_title: Titolo della finestra
            width: Larghezza personalizzata (None per dimensioni originali)
            height: Altezza personalizzata (None per dimensioni originali)
            loop: True per riproduzione in loop
            transparency: Trasparenza della finestra (1.0 = opaco, 0.0 = trasparente)
        """
        self.media_path = media_path
        self.window_title = window_title
        self.width = width
        self.height = height
        self.loop = loop
        self.transparency = transparency
        self.running = False
        self.thread = None
        self.window = None
        self.cap = None

    def _detect_media_type(self) -> str:
        """Rileva il tipo di media (video o immagine)."""
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']
        image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff']

        ext = self.media_path.lower()
        if any(ext.endswith(vid_ext) for vid_ext in video_extensions):
            return 'video'
        elif any(ext.endswith(img_ext) for img_ext in image_extensions):
            return 'image'
        else:
            # Prova a aprire come video, se fallisce assume immagine
            cap = cv2.VideoCapture(self.media_path)
            if cap.isOpened():
                cap.release()
                return 'video'
            return 'image'

    def _setup_window(self):
        """Configura la finestra Tkinter senza bordi."""
        self.window = tk.Tk()
        self.window.title(self.window_title)
        self.window.overrideredirect(True)  # Rimuove bordi e barra del titolo
        self.window.attributes('-topmost', True)  # Mantiene in primo piano
        self.window.attributes('-alpha', self.transparency)  # Imposta trasparenza

        # Crea label per mostrare il media
        self.label = tk.Label(self.window)
        self.label.pack()

        # Centra la finestra
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()

        if self.width and self.height:
            x = (screen_width - self.width) // 2
            y = (screen_height - self.height) // 2
            self.window.geometry(f"{self.width}x{self.height}+{x}+{y}")
        else:
            # Usa dimensioni automatiche
            self.window.geometry("+%d+%d" % (screen_width // 4, screen_height // 4))

    def _process_frame(self, frame):
        """Elabora un singolo frame per la visualizzazione."""
        if self.width and self.height:
            frame = cv2.resize(frame, (self.width, self.height))

        # Converti BGR a RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Converti in formato PIL
        pil_image = Image.fromarray(frame_rgb)

        # Converti in formato PhotoImage per Tkinter
        tk_image = ImageTk.PhotoImage(pil_image)

        return tk_image

    def _play_video(self):
        """Riproduce il video in loop."""
        self.cap = cv2.VideoCapture(self.media_path)
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        frame_delay = int(1000 / fps) if fps > 0 else 30

        def update_frame():
            if not self.running or self.window is None:
                return

            ret, frame = self.cap.read()

            if not ret:
                if self.loop:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self.cap.read()
                else:
                    self.stop()
                    return

            if ret:
                tk_image = self._process_frame(frame)
                self.label.configure(image=tk_image)
                self.label.image = tk_image  # Mantieni riferimento

            # Pianifica il prossimo frame
            self.window.after(frame_delay, update_frame)

        update_frame()

    def _show_image(self):
        """Mostra un'immagine statica o animata."""
        try:
            # Prova ad aprire come immagine PIL (supporta GIF animati)
            pil_image = Image.open(self.media_path)

            if pil_image.format == 'GIF' and pil_image.is_animated:
                # Gestisci GIF animato
                frames = []
                for i in range(pil_image.n_frames):
                    pil_image.seek(i)
                    frame = pil_image.copy()

                    # Converti in RGB se necessario
                    if frame.mode != 'RGB':
                        frame = frame.convert('RGB')

                    # Ridimensiona se necessario
                    if self.width and self.height:
                        frame = frame.resize((self.width, self.height), Image.Resampling.LANCZOS)

                    tk_frame = ImageTk.PhotoImage(frame)
                    frames.append(tk_frame)

                def animate_gif(idx=0):
                    if not self.running or self.window is None:
                        return

                    self.label.configure(image=frames[idx])
                    self.label.image = frames[idx]

                    next_idx = (idx + 1) % len(frames)
                    delay = pil_image.info.get('duration', 100)
                    self.window.after(delay, lambda: animate_gif(next_idx))

                animate_gif()
            else:
                # Immagine statica
                if self.width and self.height:
                    pil_image = pil_image.resize((self.width, self.height), Image.Resampling.LANCZOS)

                tk_image = ImageTk.PhotoImage(pil_image)
                self.label.configure(image=tk_image)
                self.label.image = tk_image

        except Exception as e:
            print(f"Errore nel caricamento dell'immagine: {e}")
            self.stop()

    def _run(self):
        """Metodo principale eseguito nel thread."""
        try:
            self._setup_window()
            media_type = self._detect_media_type()

            if media_type == 'video':
                self._play_video()
            else:
                self._show_image()

            # Avvia il loop principale di Tkinter
            self.window.mainloop()

        except Exception as e:
            print(f"Errore nella schermata di caricamento: {e}")
        finally:
            self._cleanup()

    def _cleanup(self):
        """Pulisce le risorse."""
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

    def start(self):
        """Avvia la schermata di caricamento in un thread separato."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

            # Attendi che la finestra sia pronta
            for _ in range(50):  # Timeout di 5 secondi
                if self.window is not None:
                    break
                time.sleep(0.1)

    def stop(self):
        """Ferma e chiude la schermata di caricamento."""
        self.running = False

        # Chiudi la finestra Tkinter
        if self.window:
            try:
                self.window.quit()
                self.window.destroy()
            except:
                pass

        # Attendi che il thread termini
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        self._cleanup()