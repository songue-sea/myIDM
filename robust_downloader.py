import requests
import os
from tqdm import tqdm
import time # Nous allons l'utiliser pour simuler un petit délai en cas d'erreur ou de retry
import threading


def download_file_robust(url, destination_folder="downloads", progress_callback=None, status_callback=None):
    """
    Télécharge un fichier depuis une URL donnée vers un dossier de destination,
    avec gestion des noms de fichiers existants et erreurs plus détaillées.
    Utilise des callbacks pour mettre à jour la progression et le statut dans une GUI.

    Args:
        url (str): L'URL du fichier à télécharger.
        destination_folder (str): Le dossier où enregistrer le fichier.
                                  Créé s'il n'existe pas.
        progress_callback (callable, optional): Fonction à appeler pour mettre à jour la progression.
                                                Prend (bytes_download, total_bytes) en args.
        status_callback (callable, optional): Fonction à appeler pour mettre à jour le statut.
                                                Prend (message, is_error=False) en args.
    """

    def update_status(message, is_error=False):
        if status_callback:
            status_callback(message, is_error)
        else:
            print(message) # sinon on affiche dans la console

    def update_progress(current, total):
        if progress_callback:
            progress_callback(current, total)


    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
        update_status(f"Dossier de destination créé : {destination_folder}")


    # Gérer les noms de fichiers pour éviter les écrasements
    original_file_name = url.split('/')[-1]
    file_name = original_file_name
    counter = 1
    while os.path.exists(os.path.join(destination_folder, file_name)):
        # Si le fichier existe, ajoute un suffixe (e.g., fichier (1).txt)
        name_parts = os.path.splitext(original_file_name) # Sépare nom et extension
        file_name = f"{name_parts[0]} ({counter}){name_parts[1]}"
        counter += 1

    file_path = os.path.join(destination_folder, file_name)

    update_status(f"Préparation du téléchargement de : {url}")
    update_status(f"Enregistrement sous : {file_path}")

    try:
        response = requests.get(url, stream=True, timeout=10) # Ajout d'un timeout
        response.raise_for_status()

        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1 Kilobyte

        # Initialise la barre de progression tqdm
        # `disable=total_size_in_bytes == 0` désactive la barre si la taille est inconnue
        progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True, desc=file_name,
                            disable=total_size_in_bytes == 0 and progress_callback is None)

        current_download_bytes = 0

        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk:
                    file.write(chunk)
                    chunk_len = len(chunk)
                    current_download_bytes += chunk_len
                    if progress_callback:
                        update_progress(current_download_bytes, total_size_in_bytes)
                        progress_bar.update(chunk_len)
        progress_bar.close()

        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            update_status(f"⚠️ AVERTISSEMENT : Le téléchargement de '{file_name}' n'est pas complet (taille attendue: {total_size_in_bytes}, téléchargée: {progress_bar.n}).")
        elif total_size_in_bytes == 0:
            update_status(f"Téléchargement de '{file_name}' terminé. Taille du fichier inconnue (pas de Content-Length).")
        else:
            update_status(f"✅ Téléchargement de '{file_name}' terminé avec succès.")

    except requests.exceptions.HTTPError as e:
        update_status(f"❌ Erreur HTTP lors du téléchargement de {url}: {e.response.status_code} - {e.response.reason}")
    except requests.exceptions.ConnectionError as e:
        update_status(f"❌ Erreur de connexion : Impossible de se connecter à {url}. Vérifiez votre connexion Internet ou l'URL. Détails: {e}")
    except requests.exceptions.Timeout as e:
        update_status(f"❌ Délai de connexion dépassé : Le serveur n'a pas répondu à temps pour {url}. Détails: {e}")
    except requests.exceptions.RequestException as e:
        update_status(f"❌ Une erreur générale de requête s'est produite lors du téléchargement de {url}: {e}")
    except Exception as e:
        update_status(f"❌ Une erreur inattendue s'est produite lors du traitement de {url}: {e}")

if __name__ == "__main__":
    # Testez avec une URL qui fonctionnait avant
    test_url_1 = "https://fr.getsamplefiles.com/download/pdf/sample-5.pdf"
    download_file_robust(test_url_1)

    # Testez la gestion des fichiers existants en téléchargeant le même fichier
    print("\n--- Test de la gestion des fichiers existants ---")
    time.sleep(2) # Petite pause pour une meilleure visibilité
    download_file_robust(test_url_1)

    # Testez avec une URL qui n'existe pas (404 Not Found)
    print("\n--- Test d'une URL non trouvée ---")
    time.sleep(2)
    test_url_404 = "https://www.learningcontainer.com/wp-content/uploads/2020/07/FICHIER_INEXISTANT.txt"
    download_file_robust(test_url_404)

    # Testez avec une URL malformée ou sans serveur (peut prendre du temps ou échouer rapidement)
    print("\n--- Test d'une URL malformée/connexion impossible ---")
    time.sleep(2)
    test_url_bad_connection = "http://serveur.nexiste.pas/fichier.txt"
    download_file_robust(test_url_bad_connection)