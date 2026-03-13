import os
import zipfile

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        # Exclude unwanted directories
        dirs[:] = [d for d in dirs if d not in ['.venv', '.git', '__pycache__', '.vscode', '.pytest_cache', '_legacy']]
        for file in files:
            if file.endswith('.zip'):
                continue
            file_path = os.path.join(root, file)
            # Add file to zip
            arc_name = os.path.relpath(file_path, path)
            ziph.write(file_path, arc_name)

if __name__ == '__main__':
    zip_filename = 'paris-bins-ml-colab.zip'
    print(f"Creating {zip_filename}...")
    zipf = zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED)
    zipdir('.', zipf)
    zipf.close()
    print("Done!")
