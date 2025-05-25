import subprocess
import os
import requests


UPLOAD_URL = "https://hytechracing.duckdns.org/mcaps/bulk_upload"

file = "test-mcap.mcap"
base_name = os.path.splitext(file)[0]
recovered_filename = f"{base_name}-recovered.mcap"
recovered_path = f"/home/krish/Documents/Github/data_offload_service/{recovered_filename}"

result = subprocess.run(
                        ["mcap", "recover", file, "-o", recovered_path],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )

print(result)

with open(recovered_path, 'rb') as f: 
                        files = {
                            'files': f
                        }

                        response = requests.post(UPLOAD_URL, files=files)
                        print(response)