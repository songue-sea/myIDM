import os
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
from robust_downloader import download_file_robust # Pour les téléchargements directs
from streaming_downloader import download_streaming_video # Nouveau: Pour les téléchargements de streaming

class DownloadManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Configuration de la Fenêtre ---
        self.title("Mon Gestionnaire de Téléchargements")
        self.geometry("600x450") # Augmentation de la taille pour les nouvelles options
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- Widgets de l'Interface ---

        # Cadre principal pour le contenu
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # Tabview pour choisir le type de téléchargement (Direct ou Streaming)
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(pady=10, padx=10, fill="both", expand=True)

        self.tabview.add("Téléchargement Direct")
        self.tabview.add("Téléchargement Streaming")

        # --- Contenu de l'onglet "Téléchargement Direct" ---
        self.direct_tab = self.tabview.tab("Téléchargement Direct")
        self.setup_direct_download_tab(self.direct_tab)

        # --- Contenu de l'onglet "Téléchargement Streaming" ---
        self.streaming_tab = self.tabview.tab("Téléchargement Streaming")
        self.setup_streaming_download_tab(self.streaming_tab)

        # Labels et barre de progression communs
        self.progress_bar = ctk.CTkProgressBar(self, mode="determinate")
        self.progress_bar.pack(pady=10, padx=20, fill="x")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Prêt à télécharger...", wraplength=550)
        self.status_label.pack(pady=10, padx=20, fill="x", anchor="w")

    # --- Méthodes pour configurer les onglets ---

    def setup_direct_download_tab(self, tab):
        # Labels et champs de saisie existants, repackagés pour l'onglet
        url_label = ctk.CTkLabel(tab, text="URL du fichier (Direct) :")
        url_label.pack(pady=(10, 0), padx=10, anchor="w")

        self.direct_url_entry = ctk.CTkEntry(tab, placeholder_text="Entrez l'URL ici...", width=500)
        self.direct_url_entry.pack(pady=(0, 10), padx=10, fill="x")

        dest_label = ctk.CTkLabel(tab, text="Dossier de destination :")
        dest_label.pack(pady=(10, 0), padx=10, anchor="w")

        dest_frame = ctk.CTkFrame(tab, fg_color="transparent")
        dest_frame.pack(pady=(0, 10), padx=10, fill="x")

        self.direct_dest_entry = ctk.CTkEntry(dest_frame, placeholder_text="Sélectionnez un dossier...", width=400)
        self.direct_dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        # Définir le dossier par défaut (par exemple, le dossier 'downloads' dans le répertoire du script)
        self.default_download_dir = os.path.join(os.getcwd(), "downloads")
        if not os.path.exists(self.default_download_dir):
            os.makedirs(self.default_download_dir)
        self.direct_dest_entry.insert(0, self.default_download_dir)

        browse_button = ctk.CTkButton(dest_frame, text="Parcourir", command=self.browse_direct_folder)
        browse_button.pack(side="right")

        download_button = ctk.CTkButton(tab, text="Télécharger (Direct)", command=self.start_direct_download_thread)
        download_button.pack(pady=10, padx=10)
        self.direct_download_button = download_button # Garde une référence au bouton

    def setup_streaming_download_tab(self, tab):
        # Labels et champs de saisie pour l'onglet streaming
        url_label = ctk.CTkLabel(tab, text="URL de la Vidéo/Page (Streaming) :")
        url_label.pack(pady=(10, 0), padx=10, anchor="w")

        self.streaming_url_entry = ctk.CTkEntry(tab, placeholder_text="Entrez l'URL de la vidéo streaming ici...", width=500)
        self.streaming_url_entry.pack(pady=(0, 10), padx=10, fill="x")

        dest_label = ctk.CTkLabel(tab, text="Dossier de destination :")
        dest_label.pack(pady=(10, 0), padx=10, anchor="w")

        dest_frame = ctk.CTkFrame(tab, fg_color="transparent")
        dest_frame.pack(pady=(0, 10), padx=10, fill="x")

        self.streaming_dest_entry = ctk.CTkEntry(dest_frame, placeholder_text="Sélectionnez un dossier...", width=400)
        self.streaming_dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        # Définir le dossier par défaut
        self.streaming_dest_entry.insert(0, self.default_download_dir) # Réutilise le même dossier par défaut

        browse_button = ctk.CTkButton(dest_frame, text="Parcourir", command=self.browse_streaming_folder)
        browse_button.pack(side="right")

        download_button = ctk.CTkButton(tab, text="Télécharger (Streaming)", command=self.start_streaming_download_thread)
        download_button.pack(pady=10, padx=10)
        self.streaming_download_button = download_button # Garde une référence au bouton


    # --- Méthodes de la Classe (Modifiées et Nouvelles) ---

    def browse_direct_folder(self):
        """Ouvre une boîte de dialogue pour sélectionner un dossier de destination pour le direct."""
        folder_selected = filedialog.askdirectory(initialdir=self.direct_dest_entry.get())
        if folder_selected:
            self.direct_dest_entry.delete(0, tk.END)
            self.direct_dest_entry.insert(0, folder_selected)

    def browse_streaming_folder(self):
        """Ouvre une boîte de dialogue pour sélectionner un dossier de destination pour le streaming."""
        folder_selected = filedialog.askdirectory(initialdir=self.streaming_dest_entry.get())
        if folder_selected:
            self.streaming_dest_entry.delete(0, tk.END)
            self.streaming_dest_entry.insert(0, folder_selected)

    def update_progress_gui(self, current, total, status_extra_info=""):
        """Callback pour mettre à jour la barre de progression et le texte."""
        if total > 0:
            progress_value = current / total
            self.progress_bar.set(progress_value)
            self.status_label.configure(text_color="white") # Réinitialise la couleur en blanc
            # Mettre à jour le statut avec le pourcentage et la taille
            self.status_label.configure(text=f"Téléchargement : {current / (1024*1024):.2f} Mo / {total / (1024*1024):.2f} Mo ({progress_value:.1%}) {status_extra_info}")
        else:
            # Si la taille totale est inconnue, afficher seulement la taille téléchargée
            self.progress_bar.set(0) # Garde la barre vide si pas de total
            self.status_label.configure(text_color="white")
            self.status_label.configure(text=f"Téléchargement : {current / (1024*1024):.2f} Mo (taille inconnue) {status_extra_info}")
        self.update_idletasks()

    def update_status_gui(self, message, is_error=False):
        """Callback pour mettre à jour le label de statut. Exécuté dans le thread principal de Tkinter."""
        # Utiliser after pour s'assurer que les mises à jour UI sont sur le thread principal
        def _update():
            if is_error:
                self.status_label.configure(text=f"ERREUR: {message}", text_color="red")
            else:
                self.status_label.configure(text=message, text_color="green" if "succès" in message or "terminé" in message else "white")
            self.update_idletasks()
        self.after(0, _update)


    def start_direct_download_thread(self):
        """Démarre le téléchargement direct dans un thread séparé."""
        url = self.direct_url_entry.get()
        destination = self.direct_dest_entry.get()
        if not url:
            messagebox.showwarning("URL Manquante", "Veuillez entrer une URL à télécharger.")
            return

        self._reset_ui_for_download()
        self.direct_download_button.configure(state="disabled", text="Téléchargement en cours...")

        download_thread = threading.Thread(target=self._run_direct_download, args=(url, destination))
        download_thread.start()

    def _run_direct_download(self, url, destination):
        """Fonction interne exécutée dans le thread de téléchargement direct."""
        try:
            download_file_robust(url, destination,
                                 progress_callback=self.update_progress_gui,
                                 status_callback=self.update_status_gui)
        finally:
            self.direct_download_button.configure(state="normal", text="Télécharger (Direct)")
            if "succès" in self.status_label.cget("text") and self.progress_bar.get() < 1:
                self.progress_bar.set(1)

    def start_streaming_download_thread(self):
        """Démarre le téléchargement streaming dans un thread séparé."""
        url = self.streaming_url_entry.get()
        destination = self.streaming_dest_entry.get()
        if not url:
            messagebox.showwarning("URL Manquante", "Veuillez entrer une URL de vidéo streaming.")
            return

        self._reset_ui_for_download()
        self.streaming_download_button.configure(state="disabled", text="Téléchargement en cours...")

        download_thread = threading.Thread(target=self._run_streaming_download, args=(url, destination))
        download_thread.start()

    def _run_streaming_download(self, url, destination):
        """Fonction interne exécutée dans le thread de téléchargement streaming."""
        try:
            download_streaming_video(url, destination,
                                    progress_callback=self.update_progress_gui,
                                    status_callback=self.update_status_gui)
        finally:
            self.streaming_download_button.configure(state="normal", text="Télécharger (Streaming)")
            # La barre de progression pour yt-dlp est plus délicate, il faut s'assurer qu'elle se remplit
            # _report_hook devrait gérer de mettre progress_bar à 1.0 à la fin.


    def _reset_ui_for_download(self):
        """Réinitialise l'UI avant un nouveau téléchargement."""
        self.progress_bar.set(0)
        self.status_label.configure(text="Démarrage du téléchargement...", text_color="white")


# --- Point d'entrée de l'Application ---
if __name__ == "__main__":
    app = DownloadManagerApp()
    app.mainloop()