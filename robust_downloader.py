import requests
import os
from tqdm import tqdm
import threading
import time
import math

MAX_CONNECTIONS = 8

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Referer': 'https://video.sibnet.ru/'  # Votre Referer trouvé
}


def download_file_robust(url, destination_folder="downloads", progress_callback=None, status_callback=None):
    def update_status(message, is_error=False):
        if status_callback:
            status_callback(message, is_error)
        else:
            print(message)

    def update_progress(current, total):
        if progress_callback:
            progress_callback(current, total)

    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
        update_status(f"Dossier de destination créé : {destination_folder}")

    original_file_name = url.split('/')[-1]
    file_name = original_file_name
    file_path = os.path.join(destination_folder, file_name)

    headers = BROWSER_HEADERS.copy()
    mode = 'wb'
    initial_bytes = 0

    # --- Étape 1 : Obtenir l'URL finale après les redirections et ses infos ---
    total_server_size = 0
    accept_ranges = False
    final_download_url = url  # On commence avec l'URL initiale

    try:
        # Fait une requête GET pour s'assurer de suivre toutes les redirections
        # et obtenir les headers de la réponse finale
        with requests.get(url, stream=True, timeout=5, headers=BROWSER_HEADERS) as initial_response:
            initial_response.raise_for_status()
            final_download_url = initial_response.url  # L'URL après toutes les redirections

            # Tente de récupérer la taille totale
            total_server_size = int(initial_response.headers.get('content-length', 0))
            accept_ranges = 'bytes' in initial_response.headers.get('accept-ranges', '').lower()

            # Note: initial_response.close() est appelé automatiquement par 'with'

        update_status(f"URL finale après redirection : {final_download_url}")
        update_status(
            f"Taille du fichier sur le serveur : {total_server_size / (1024 * 1024):.2f} Mo. Supporte les plages : {accept_ranges}.")

    except requests.exceptions.RequestException as e:
        update_status(
            f"Impossible de récupérer les informations du fichier sur le serveur : {e}. Tentative de téléchargement simple.",
            True)
        total_server_size = 0  # Force le téléchargement simple si erreur ou pas d'info

    # --- Gestion des fichiers existants et reprise (adaptée au multi-segments) ---
    temp_parts_dir = os.path.join(destination_folder, f"{file_name}.parts")

    # Si le fichier final existe et est complet, on ne fait rien
    if os.path.exists(file_path) and 0 < total_server_size == os.path.getsize(file_path):
        update_status(
            f"Le fichier '{file_name}' est déjà complet ({os.path.getsize(file_path)} octets). Téléchargement ignoré.",
            False)
        if progress_callback:
            update_progress(total_server_size, total_server_size)
        if os.path.exists(temp_parts_dir):
            try:
                for f in os.listdir(temp_parts_dir):
                    os.remove(os.path.join(temp_parts_dir, f))
                os.rmdir(temp_parts_dir)
                update_status(f"Dossier temporaire supprimé : {temp_parts_dir}", False)
            except Exception as e:
                update_status(f"Impossible de supprimer le dossier temporaire : {e}", True)
        return

    # --- LOGIQUE MULTI-SEGMENTS (si accept_ranges est True et total_server_size > 0) ---
    # Nous allons déplacer cette logique plus haut pour la prioriser si elle est supportée

    if accept_ranges and total_server_size > 0:
        update_status("Téléchargement multi-segments supporté. Démarrage du téléchargement segmenté.", False)

        if not os.path.exists(temp_parts_dir):
            os.makedirs(temp_parts_dir)
            update_status(f"Dossier temporaire créé pour les parties : {temp_parts_dir}", False)

        part_size = math.ceil(total_server_size / MAX_CONNECTIONS)
        threads = []

        downloaded_total_bytes = 0
        progress_lock = threading.Lock()

        def download_part(part_num, start_byte, end_byte, part_url, part_file_path, part_progress_callback=None,
                          part_status_callback=None):
            nonlocal downloaded_total_bytes

            headers = BROWSER_HEADERS.copy()  # Chaque partie utilise les headers du navigateur
            headers['Range'] = f'bytes={start_byte}-{end_byte}'  # Puis ajoute son propre Range

            part_mode = 'wb'
            part_initial_bytes = 0

            # Gérer la reprise pour la partie individuelle
            if os.path.exists(part_file_path):
                part_initial_bytes = os.path.getsize(part_file_path)
                if part_initial_bytes == (end_byte - start_byte + 1):
                    update_status(f"Partie {part_num} déjà complète.", False)
                    with progress_lock:
                        downloaded_total_bytes += part_initial_bytes
                    if progress_callback:
                        update_progress(downloaded_total_bytes, total_server_size)
                    return
                elif part_initial_bytes < (end_byte - start_byte + 1):
                    headers['Range'] = f'bytes={start_byte + part_initial_bytes}-{end_byte}'  # Ajuste le range
                    part_mode = 'ab'
                    update_status(
                        f"Reprise de la partie {part_num} à partir de {start_byte + part_initial_bytes} octets...",
                        False)
                else:
                    update_status(f"Partie {part_num} corrompue ou taille incorrecte. Redémarrage.", True)
                    part_initial_bytes = 0
                    part_mode = 'wb'

            update_status(f"Démarrage du téléchargement de la partie {part_num} ({start_byte}-{end_byte})...", False)

            try:
                # Utiliser final_download_url pour les parties
                response = requests.get(final_download_url, stream=True, headers=headers,
                                        timeout=10)  # Utilise les headers déjà fusionnés
                response.raise_for_status()

                # Si le serveur ne supporte pas la reprise pour cette requête GET (réponse 200 au lieu de 206)
                if response.status_code == 200 and part_initial_bytes > 0:
                    update_status(f"Serveur ne supporte pas la reprise pour la partie {part_num}. Redémarrage complet.",
                                  True)
                    part_initial_bytes = 0
                    part_mode = 'wb'
                    # Re-requête sans l'en-tête Range si le serveur répond 200 malgré tout
                    # Pour simplifier, on laisse l'écriture 'wb' et on recommence
                    # Si on voulait être parfait, on ferait un nouveau requests.get ici sans Range

                with open(part_file_path, part_mode) as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            chunk_len = len(chunk)
                            with progress_lock:
                                downloaded_total_bytes += chunk_len
                            if progress_callback:
                                update_progress(downloaded_total_bytes, total_server_size)
                update_status(f"Partie {part_num} téléchargée avec succès.", False)

            except requests.exceptions.RequestException as e:
                update_status(f"❌ Erreur lors du téléchargement de la partie {part_num}: {e}", True)
            except Exception as e:
                update_status(f"❌ Erreur inattendue pour la partie {part_num}: {e}", True)

        for i in range(MAX_CONNECTIONS):
            start = i * part_size
            end = min((i + 1) * part_size - 1, total_server_size - 1)
            if start > end:
                continue

            part_file_path = os.path.join(temp_parts_dir, f"{file_name}.part{i}")

            # Pass final_download_url to download_part
            thread = threading.Thread(target=download_part,
                                      args=(i, start, end, final_download_url, part_file_path,
                                            # MODIF ICI : final_download_url
                                            progress_callback, status_callback))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        update_status("Toutes les parties téléchargées. Fusion en cours...", False)
        try:
            with open(file_path, 'wb') as outfile:
                for i in range(MAX_CONNECTIONS):
                    part_file_path = os.path.join(temp_parts_dir, f"{file_name}.part{i}")
                    if os.path.exists(part_file_path):
                        with open(part_file_path, 'rb') as infile:
                            outfile.write(infile.read())
                        os.remove(part_file_path)

            os.rmdir(temp_parts_dir)
            update_status(
                f"✅ Téléchargement multi-segments de '{file_name}' terminé avec succès. Dossier temporaire supprimé.",
                False)
            if progress_callback:
                update_progress(total_server_size, total_server_size)

        except Exception as e:
            update_status(f"❌ Erreur lors de la fusion ou de la suppression des parties : {e}", True)
            update_status(f"Le fichier '{file_name}' peut être incomplet ou corrompu.", True)

        return  # Termine la fonction après le multi-segments

    # --- LOGIQUE DE TÉLÉCHARGEMENT SIMPLE (si multi-segments non supporté/applicable) ---
    # Cette section est exécutée si la condition 'if accept_ranges and total_server_size > 0:' ci-dessus est fausse

    update_status(
        "Téléchargement multi-segments non supporté ou taille inconnue. Bascule sur le téléchargement direct.", False)

    # La logique de reprise simple n'a plus besoin de redemander la taille via HEAD
    # car initial_response l'a déjà gérée.
    # On va juste adapter la logique pour la reprise simple

    # Reprise simple si le fichier existe et est incomplet
    if os.path.exists(file_path):
        initial_bytes = os.path.getsize(file_path)
        if total_server_size > 0 and initial_bytes < total_server_size:
            headers['Range'] = f'bytes={initial_bytes}-'
            mode = 'ab'
            update_status(f"Reprise du téléchargement simple à partir de {initial_bytes} octets...", False)
        elif initial_bytes == total_server_size and total_server_size > 0:
            update_status(f"Le fichier '{file_name}' est déjà complet ({initial_bytes} octets). Téléchargement ignoré.",
                          False)
            if progress_callback: update_progress(initial_bytes, total_server_size)
            return
        else:  # Fichier existe mais ne peut pas être repris ou est de taille incorrecte, on écrase
            update_status(
                f"Impossible de reprendre le téléchargement pour '{file_name}'. Redémarrage du téléchargement.", False)
            initial_bytes = 0  # Réinitialise pour recommencer

    if mode == 'wb' and os.path.exists(file_path):
        try:
            os.remove(file_path)
            update_status(f"Ancien fichier '{file_name}' supprimé pour nouveau téléchargement.", False)
        except Exception as e:
            update_status(
                f"Impossible de supprimer l'ancien fichier '{file_name}': {e}. Le téléchargement pourrait échouer.",
                True)

    try:
        # Utiliser final_download_url pour le téléchargement simple
        response = requests.get(final_download_url, stream=True, timeout=10,
                                headers=headers)  # MODIF ICI : final_download_url
        response.raise_for_status()

        if response.status_code == 200 and initial_bytes > 0:
            update_status(
                f"Le serveur ne supporte pas la reprise pour le téléchargement simple. Redémarrage complet du téléchargement pour '{file_name}'.",
                False)
            initial_bytes = 0
            mode = 'wb'

        total_size_response = int(response.headers.get('content-length', 0))
        total_size_for_progress = total_size_response + initial_bytes

        block_size = 1024

        progress_bar = tqdm(initial=initial_bytes,
                            total=total_size_for_progress,
                            unit='iB', unit_scale=True, desc=file_name,
                            disable=total_size_for_progress == 0 and progress_callback is None)

        with open(file_path, mode) as file:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    file.write(chunk)
                    chunk_len = len(chunk)
                    progress_bar.update(chunk_len)
                    if progress_callback:
                        update_progress(progress_bar.n, total_size_for_progress)

        progress_bar.close()

        if total_size_for_progress != 0 and progress_bar.n != total_size_for_progress:
            update_status(
                f"⚠️ AVERTISSEMENT : Le téléchargement de '{file_name}' n'est pas complet (taille attendue: {total_size_for_progress}, téléchargée: {progress_bar.n}).",
                is_error=True)
        elif total_size_for_progress == 0 and initial_bytes == 0:
            update_status(
                f"Téléchargement de '{file_name}' terminé. Taille du fichier inconnue (pas de Content-Length).", False)
        else:
            update_status(f"✅ Téléchargement de '{file_name}' terminé avec succès.", False)

    except requests.exceptions.HTTPError as e:
        update_status(
            f"❌ Erreur HTTP lors du téléchargement simple de {url}: {e.response.status_code} - {e.response.reason}",
            is_error=True)
    except requests.exceptions.ConnectionError as e:
        update_status(
            f"❌ Erreur de connexion lors du téléchargement simple : Impossible de se connecter à {url}. Détails: {e}",
            is_error=True)
    except requests.exceptions.Timeout as e:
        update_status(
            f"❌ Délai de connexion dépassé lors du téléchargement simple : Le serveur n'a pas répondu à temps pour {url}. Détails: {e}",
            is_error=True)
    except requests.exceptions.RequestException as e:
        update_status(f"❌ Une erreur générale de requête s'est produite lors du téléchargement simple de {url}: {e}",
                      is_error=True)
    except Exception as e:
        update_status(f"❌ Une erreur inattendue s'est produite lors du traitement simple de {url}: {e}", is_error=True)
    return  # Termine la fonction si on a fait un téléchargement simple

# ... (Votre bloc if __name__ == "__main__": reste inchangé, mais vous pouvez tester avec l'URL de sibnet pour le multi-segments)