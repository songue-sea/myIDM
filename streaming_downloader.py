import yt_dlp
import os
import threading
import tkinter as tk

def download_streaming_video(url, destination_folder="downloads", progress_callback=None, status_callback=None):
    """
    Télécharge une vidéo depuis une URL de streaming en utilisant yt-dlp.
    :param url: L'URL de la page vidéo (ex: YouTube, Anime-Sama))
    :type url: str
    :param destination_folder: Le dossier où enregistrer le fichier.
    :type destination_folder: str
    :param progress_callback: Fonction à appeler pour mettre à jour la progression. Prend (current_bytes, total_bytes, status_text) en param
    :type progress_callback: callable
    :param status_callback: Fonction à appeler pour mettre à jour le statut. Prend (message, is_error=False) en param
    :type status_callback: callable
    """

    def _report_hook(d):
        # Cette fonction est appelée par yt-dlp pour reporter la progression
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes')
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)

            # Mettre à jour la GUI avec la progression
            if progress_callback:
                progress_callback(downloaded_bytes, total_bytes, f"Vitesse: {speed/1024:.2f} KiB/s, Reste: {eta}s")
            # Mettre à jour le GUI avec le status général si besoin
            if status_callback:
                # utilisation de .after pour s'assurer que la mise à jour se fait dans le thread principal de Tkinter
                tk.Frame().after(0, status_callback, f"Téléchargement : {d['_percent_str']} de {d['_total_bytes_str']} (vitesse: {d['_speed_str']})", False )
        elif d['status'] == 'finished':
            if progress_callback:
                progress_callback(d.get('total_bytes', 1), d.get('total_bytes', 1), "Terminé") # s'assurer que la barre est pleine
            if status_callback:
                tk.Frame().after(0, status_callback, f"✅ Téléchargement de '{d['filename']}' terminé avec succès.",False)
        elif d['status'] == 'error':
            if status_callback:
                tk.Frame().after(0, status_callback,f"❌ Erreur lors du téléchargement: {d.get('error', 'Inconnu')}", True)

    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
        if status_callback:
            tk.Frame().after(0, status_callback, f"Dossier de destination créé : {destination_folder}", False)
        else:
            print(f"Dossier de destination créé : {destination_folder}")

    # Options pour yt-dlp
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best', # Télécharge la meilleure qualité vidéo et audio et les fusionne
        'outtmpl': os.path.join(destination_folder, "%(title)s.%(ext)s"), # Chemin de sortie avec le titre et l'extension
        'progress_hooks': [_report_hook], # Fonction de rappel pour la progression
        'merge_output_format': 'mp4', # Fusionne en mp4 si audio et vidéo sont séparés
        'noplaylist': True, # Empêche le téléchargement de playlists entières si l'URL est une playlist
    }

    try:
        if status_callback:
            tk.Frame().after(0, status_callback, f"Préparation du téléchargement de la vidéo : {url}", False)
        else:
            print(f"Préparation du téléchargement de la vidéo : {url}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        if status_callback:
            tk.Frame().after(0, status_callback, f"❌ Erreur de téléchargement vidéo : {e}", True)
        else:
            print(f"❌ Erreur de téléchargement vidéo : {e}")
    except Exception as e:
        if status_callback:
            tk.Frame().after(0, status_callback, f"❌ Une erreur inattendue s'est produite : {e}", True)
        else:
            print(f"❌ Une erreur inattendue s'est produite : {e}")

if __name__ == "__main__":
    # Exemple d'utilisation
    test_video_url = "https://youtu.be/PIwhyrZZlFw?list=RDPIwhyrZZlFw"
    print("Test de téléchargement de vidéo...")
    download_streaming_video(test_video_url)
    print("\nTest terminé.")
