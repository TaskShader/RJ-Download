# Based on https://github.com/SofiaXu/PSAsmrOnlineClient

To use the script, you'll need to install the required dependencies:
`pip install requests tqdm`

# 1 First, Login

python script.py --login --username your_username --password your_password

# Then, Search and download; Or, Download from input file

python script.py --search --keyword "伊ヶ崎綾香" --lossless-mode "Lossless"

python script.py --input-file input.json


# Modify the output pattern

Find and modify the following line: 
```
output_pattern=config.get('output_pattern', '<vas>_RJ<id>_<title>_<tags>')
```
