import requests
import os
from tqdm import tqdm

def download_file(url, destination_folder="downloads"):
    """
    Télécharge un fichier depuis une URL donnée vers un dossier de destination.

    Args :
        url (str) : l'URL du fichier à télécharger
        destination_folder (str) : Le dossier de destination
        
    """
    if not os.path.exists(destination_folder):
        os.makedirs(destination_folder)

    file_name = url.split('/')[-1] # extrait le nom du fichier de l'URL
    file_path = os.path.join(destination_folder, file_name)

    print(f"Tentative de téléchargement de : {url}")
    print(f"Vers : {file_path}")

    try:
        response = requests.get(url, stream=True) # Stream = True lit le contenu par morceaux
        response.raise_for_status()  # Lève une execption pour les erreurs

        total_size_in_bytes = int(response.headers.get('content-length', 0))
        block_size = 1024  # 1 Kilobyte

        # initialiser la barre de progression tqdm
        progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True, desc=file_name)

        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=block_size):
                if chunk: # Assurer que le morceau n'est pas vide
                    file.write(chunk)
                    progress_bar.update(len(chunk))
        progress_bar.close()

        if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
            print("ERREUR: Le Téléchargement n'est pas complet !")
        else:
            print(f"Téléchargement de '{file_name}' terminé avec succès.")
    except requests.exceptions.RequestException as e:
        print(f"Une erreur s'est produite lors du téléchargement : {e}")
    except Exception as e:
        print(f"Une erreur inattendue s'est produite : {e}")


if __name__ == "__main__":
    test_url  = "https://fr.getsamplefiles.com/download/pdf/sample-5.pdf"

    download_file(test_url)