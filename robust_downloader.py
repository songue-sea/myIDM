
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
        # La barre tqdm est gérée directement dans la boucle


    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)
        update_status(f"Dossier de destination créé : {destination_folder}")


    # Gérer les noms de fichiers pour éviter les écrasements
    original_file_name = url.split('/')[-1]
    file_name = original_file_name

    # Logique pour la reprise ou la gestion des doublons
    headers = {}
    mode = 'wb' # Mode d'écriture par défaut (binaire)
    initial_bytes = 0 # Nbre d'octets déjà téléchargés

    file_path = os.path.join(destination_folder, file_name)
    if os.path.exists(file_path):
        initial_bytes = os.path.getsize(file_path)
        update_status(f"Fichier '{file_name}' existant détecté. Taille : {initial_bytes} octets.")

        try:
            # Tente de récupérer la taille totale du fichier depuis le  serveur
            head_response = requests.head(url, timeout=5)
            head_response.raise_for_status()
            total_server_size = int(head_response.headers.get('content-length', 0))

            if total_server_size > 0 and initial_bytes < total_server_size:
                # Le fichier est incomplet , tentative de reprendre
                headers = {'Range': f'bytes={initial_bytes}-'}
                mode = 'ab' # Mode d'écriture en append (ajout binaire)
                update_status(f"Reprise du téléchargement à partir de {initial_bytes} octets...", False)
            elif initial_bytes == total_server_size and total_server_size > 0:
                # Fichier est déja complet
                update_status(f"Le fichier '{file_name}' est déjà complet ({initial_bytes} octets). Téléchargement ignoré.", False)
                if progress_callback: # Mettre à jour à 100% si déjà complet
                    update_progress(initial_bytes, total_server_size)
                return # Terminer la fonction car le fichier est déjà là
            else:
                # Le serveur n'a pas fourni de taille ou la taille existante est plus grande
                update_status(f"Impossible de reprendre le téléchargement pour '{file_name}'. Redémarrage du téléchargement.", False)
                # on ne modifie pas le file_name ici, on écrase l'ancien
                initial_bytes = 0 # Réinitialise pour commencer
                # On ne change pas le mode aussi (wb par défaut)
        except requests.exceptions.RequestException as e:
            update_status(f"Impossible de vérifier la taille du fichier sur le serveur pour reprise : {e}. Redémarrage du téléchargement.", True)
            initial_bytes = 0

    # Si le fichier n'existe pas du tout, on utilise le nom original
    # Si on reprend, le nom est le même.
    # Si on redémarre (pas de reprise possible), le nom est le même
    # Seule la logique des doublons se déclenche si on veut garder l'ancien et recommencer.
    # Pour l'instant, si on ne peut pas reprendre, on écrase.
    # Pour éviter d'écraser si la reprise est impossible et qu'on veut garder l'ancien, on peut ajouter une option ici.
    # Pour l'objectif actuel, on va gérer l'écrasement ou la reprise.

    # Si on est en mode 'wb' et que le fichier existe, on le supprime avant de commencer pour éviter l'append accidentel
    if mode == 'wb' and os.path.exists(file_path):
        try:
            os.remove(file_path)
            update_status(f"Ancien fichier '{file_name}' supprimé pour nouveau téléchargement.", False)
        except Exception as e:
            update_status(f"Impossible de supprimer l'ancien fichier '{file_name}': {e}. Le téléchargement pourrait échouer.", True)

    update_status(f"Démarrage du téléchargement de : {url}")
    update_status(f"Enregistrement sous : {file_path}")

    try:
        response = requests.get(url, stream=True, headers=headers, timeout=10) # Ajout des headers pour la reprise
        response.raise_for_status()

        # Si le serveur ne supporte pas la reprise , il envoie 200 au lieu de 206
        if response.status_code == 200 and initial_bytes > 0:
            update_status(f"Le serveur ne supporte pas la reprise. Redémarrage complet du téléchargement pour '{file_name}'.", False)
            initial_bytes = 0
            mode = 'wb'
            # Attention: ici on devrait redemander la taille totale car le content-length peut être pour le fichier complet
            # On va simplifier pour l'instant et refaire la requête si le 200 est reçu
            # Pour l'instant, on laisse response tel quel et gère les octets initiaux dans total_size

            # Pour être parfait, il faudrait refaire une requête GET SANS Range header ici
            # Mais pour simplifier, on continue avec cette réponse, en sachant que initial_bytes est 0

        # La taille totale du fichier sera la taille sur le serveur.
        # Si on reprend, le content-length de la réponse sera la taille restante à télécharger.
        # Il faut donc ajouter initial_bytes à ce content-length pour avoir la taille totale du fichier.
        total_size_response = int(response.headers.get('content-length', 0))
        total_size_in_bytes = total_size_response + initial_bytes

        block_size = 1024

        progress_bar = tqdm(initial=initial_bytes,
                        total=total_size_in_bytes,
                        unit='iB', unit_scale=True, desc=file_name,
                        disable=total_size_in_bytes == 0 and progress_callback is None)

        with open(file_path, mode) as file:
            for chunk in response.iter_content(block_size):
                if chunk:
                    file.write(chunk)
                    chunk_length = len(chunk)
                    progress_bar.update(chunk_length)
                    if progress_callback:
                        update_progress(progress_bar.n, total_size_in_bytes)

        progress_bar.close()

        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            update_status(f"⚠️ AVERTISSEMENT : Le téléchargement de '{file_name}' n'est pas complet (taille attendue: {total_size_in_bytes}, téléchargée: {progress_bar.n}).", is_error=True)
        elif total_size_in_bytes == 0 and initial_bytes == 0:
            update_status(f"Téléchargement de '{file_name}' terminé. Taille du fichier inconnue (pas de Content-Length).",False)
        else:  # Si total_size_in_bytes est 0 mais initial_bytes > 0, c'est que le fichier est déjà complet
            update_status(f"✅ Téléchargement de '{file_name}' terminé avec succès.", False)
    except requests.exceptions.HTTPError as e:
        update_status(f"❌ Erreur HTTP lors du téléchargement de {url}: {e.response.status_code} - {e.response.reason}",
                      is_error=True)
    except requests.exceptions.ConnectionError as e:
        update_status(
            f"❌ Erreur de connexion : Impossible de se connecter à {url}. Vérifiez votre connexion Internet ou l'URL. Détails: {e}",
            is_error=True)
    except requests.exceptions.Timeout as e:
        update_status(f"❌ Délai de connexion dépassé : Le serveur n'a pas répondu à temps pour {url}. Détails: {e}",
                      is_error=True)
    except requests.exceptions.RequestException as e:
        update_status(f"❌ Une erreur générale de requête s'est produite lors du téléchargement de {url}: {e}",
                      is_error=True)
    except Exception as e:
        update_status(f"❌ Une erreur inattendue s'est produite lors du traitement de {url}: {e}", is_error=True)

# Le bloc if __name__ == "__main__": doit être mis à jour pour tester la reprise
if __name__ == "__main__":
    # URL de test pour la reprise (un fichier un peu plus gros est mieux pour tester)
    # Utilisez un fichier que vous pouvez interrompre.
    test_url_resume = "https://fr.getsamplefiles.com/download/rar/sample-3.rar" # Fichier binaire de 100 Mo

    print("--- Test de la reprise du téléchargement ---")
    # Premier téléchargement (vous pouvez l'interrompre manuellement en fermant la console PyCharm)
    print("Premier téléchargement. Essayez de l'interrompre après quelques secondes (Ctrl+C ou fermer la fenêtre)")
    download_file_robust(test_url_resume)

    print("\n--- Tentative de reprise du téléchargement ---")
    # Deuxième appel : il devrait reprendre là où il s'est arrêté
    time.sleep(2) # Pause pour la visibilité
    download_file_robust(test_url_resume)

    print("\n--- Test d'un fichier déjà complet ---")
    time.sleep(2)
    download_file_robust(test_url_resume) # Il devrait dire que le fichier est complet

    # Autres tests existants
    print("\n--- Test de la gestion des fichiers existants (non-reprise) ---")
    time.sleep(2)
    download_file_robust("https://www.learningcontainer.com/wp-content/uploads/2020/07/20MB.txt")
    download_file_robust("https://www.learningcontainer.com/wp-content/uploads/2020/07/20MB.txt")


    print("\n--- Test d'une URL non trouvée ---")
    time.sleep(2)
    test_url_404 = "https://www.learningcontainer.com/wp-content/uploads/2020/07/FICHIER_INEXISTANT.txt"
    download_file_robust(test_url_404)

    print("\n--- Test d'une URL malformée/connexion impossible ---")
    time.sleep(2)
    test_url_bad_connection = "http://serveur.nexiste.pas/fichier.txt"
    download_file_robust(test_url_bad_connection)