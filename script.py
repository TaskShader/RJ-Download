import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple, Union
import requests
from tqdm import tqdm

@dataclass
class Config:
    token: str
    lossless_mode: str = "All"
    output_pattern: str = "RJ<id><title><vas><tags>"

class ASMROneAPI:
    BASE_URL = "https://api.asmr.one/api"
    HEADERS = {
        "accept": "application/json, text/plain, */*",
        "dnt": "1",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "Windows",
        "origin": "https://www.asmr.one",
        "sec-fetch-site": "same-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://www.asmr.one/",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
    }

    def __init__(self, token: Optional[str] = None):
        self.token = token
        if token:
            self.HEADERS["authorization"] = f"Bearer {token}"

    def authenticate(self, username: str, password: str) -> dict:
        url = f"{self.BASE_URL}/auth/me"
        response = requests.post(url, headers=self.HEADERS, json={
            "name": username,
            "password": password
        })
        return response.json()

    def search_works(self, keyword: str, page: int = 1, order: str = 'release', sort: str = 'desc') -> dict:
        url = f"{self.BASE_URL}/search/{keyword}"
        params = {
            "order": order,
            "sort": sort,
            "page": page,
            "subtitle": 0,
            "seed": 80
        }
        response = requests.get(url, headers=self.HEADERS, params=params)
        return response.json()
    
    def search_all_pages(self, keyword: str, order: str = 'release', sort: str = 'desc') -> List[dict]:
        """Get all works across all pages for a given search"""
        all_works = []
        page = 1
        while True:
            params = {
                "order": order,
                "sort": sort,
                "page": page,
                "subtitle": 0,
                "seed": 80
            }
            url = f"{self.BASE_URL}/search/{keyword}"
            response = requests.get(url, headers=self.HEADERS, params=params)
            data = response.json()
            works = data.get('works', [])
            if not works:
                break
                
            all_works.extend(works)
            
            # Check if we've reached the last page
            pagination = data.get('pagination', {})
            current_page = pagination.get('currentPage', 1)
            total_count = pagination.get('totalCount', 0)
            page_size = pagination.get('pageSize', 20)
            total_pages = (total_count + page_size - 1) // page_size
            
            print(f"Fetched page {current_page} of {total_pages} ({len(works)} works)")
            
            if current_page >= total_pages:
                break
                
            page += 1
            
        return all_works
        

    def get_work(self, rj_number: str) -> dict:
        rj_number = rj_number.replace('RJ', '')
        url = f"{self.BASE_URL}/work/{rj_number}"
        response = requests.get(url, headers=self.HEADERS)
        return response.json()

    def get_tracks(self, rj_number: str) -> dict:
        rj_number = rj_number.replace('RJ', '')
        url = f"{self.BASE_URL}/tracks/{rj_number}"
        response = requests.get(url, headers=self.HEADERS)
        return response.json()

class Downloader:
    def __init__(self, config: Config):
        self.config = config
        self.api = ASMROneAPI(config.token)

    def format_output_path(self, work: dict) -> str:
        '''
        <id> | RJ Number
        <title> | Title
        <vas> | Voice Actors
        <tags> | Tags
        '''
        pattern = self.config.output_pattern
        pattern = pattern.replace("<id>", str(work['id']))
        pattern = pattern.replace("<title>", work['title'].replace("\\", "_").replace("/", "_"))
        pattern = pattern.replace("<circle>", work['name'].replace("\\", "_").replace("/", "_"))
        
        vas = ",".join([va['name'] for va in work.get('vas', [])])
        pattern = pattern.replace("<vas>", vas.replace("\\", "_").replace("/", "_"))
        
        tags = ",".join([tag['name'] for tag in work.get('tags', [])])
        pattern = pattern.replace("<tags>", tags.replace("\\", "_").replace("/", "_"))
        
        
        return pattern

    def should_download_track(self, track_title: str) -> bool:
        is_lossless = bool(re.search(r'\.(wav|flac)$', track_title))
        
        if self.config.lossless_mode == "Lossless":
            return is_lossless
        elif self.config.lossless_mode == "Lossy":
            return not is_lossless
        return True

    def get_track_list(self, tracks: List[dict], out_directory: str) -> List[Tuple[str, str]]:
        download_list = []
        
        for track in tracks:
            if track['type'] == 'folder':
                folder_path = os.path.join(out_directory, track['title'].replace("\\", "_").replace("/", "_"))
                sub_tracks = self.get_track_list(track['children'], folder_path)
                download_list.extend(sub_tracks)
                continue

            title = track['title'].replace("\\", "_").replace("/", "_")
            url = track['mediaDownloadUrl']
            out_file = os.path.join(out_directory, title)

            if track['type'] == 'audio':
                if self.should_download_track(title):
                    download_list.append((url, out_file))
            else:
                download_list.append((url, out_file))

        if download_list and not os.path.exists(out_directory):
            os.makedirs(out_directory)

        return download_list

    def download_file(self, url: str, destination: str):
        response = requests.get(url, headers=self.api.HEADERS, stream=True)
        total_size = int(response.headers.get('content-length', 0))

        with open(destination, 'wb') as file, tqdm(
            desc=os.path.basename(destination),
            total=total_size,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            for data in response.iter_content(chunk_size=1024):
                size = file.write(data)
                pbar.update(size)

    def download_work(self, rj_number: str):
        work = self.api.get_work(rj_number)
        out_directory = self.format_output_path(work)
        print(f"Start Download: {work['title']} into {out_directory}")

        tracks = self.api.get_tracks(rj_number)
        download_list = self.get_track_list(tracks, out_directory)

        for url, destination in download_list:
            self.download_file(url, destination)

        # Save work info
        with open(os.path.join(out_directory, "workInfo.json"), 'w', encoding='utf-8') as f:
            json.dump(work, f, ensure_ascii=False, indent=2)

        print(f"Finished Download: {work['title']} into {work['id']}")

def parse_range_selection(selection_str: str, max_length: int) -> List[int]:
    """
    Parse a selection string that supports individual numbers and ranges.
    Examples:
        "1,3-5,7" -> [0,2,3,4,6]
        "1-3,5,7-9" -> [0,1,2,4,6,7,8]
    """
    selected_indices = set()
    
    # Split by comma and process each part
    parts = [p.strip() for p in selection_str.split(',')]
    
    for part in parts:
        try:
            if '-' in part:
                # Handle range (e.g., "3-7")
                start, end = map(int, part.split('-'))
                if start <= end:
                    # Convert to 0-based index
                    indices = range(start - 1, end)
                    selected_indices.update(i for i in indices if 0 <= i < max_length)
            else:
                # Handle single number
                index = int(part) - 1
                if 0 <= index < max_length:
                    selected_indices.add(index)
        except ValueError:
            print(f"Warning: Skipping invalid input part: {part}")
            continue
    
    return sorted(list(selected_indices))

def display_works_and_get_selection(works: List[dict]) -> List[str]:
    """Display works and get user selection with range support"""
    # Display all works with index
    for i, work in enumerate(works):
        print(f"{i+1}. RJ{work['id']} - {work['title']}")
    
    print("\nYou can enter:")
    print("- Single numbers: 1,3,5")
    print("- Ranges: 1-5")
    print("- Combinations: 1,3-5,7,9-11")
    
    while True:
        selection = input("\nEnter the numbers of works to download: ").strip()
        
        if not selection:
            print("No input provided. Please try again.")
            continue
            
        try:
            selected_indices = parse_range_selection(selection, len(works))
            
            if not selected_indices:
                print("No valid works selected. Please try again.")
                continue
                
            # Convert to work IDs
            work_ids = [str(works[i]['id']) for i in selected_indices]
            
            # Show selection summary
            print(f"\nSelected {len(work_ids)} works:")
            for i in selected_indices:
                print(f"- RJ{works[i]['id']} - {works[i]['title']}")
            
            confirm = input("\nConfirm selection? (y/n): ").strip().lower()
            if confirm == 'y':
                return work_ids
            else:
                print("Selection cancelled. Please try again.")
                
        except Exception as e:
            print(f"Error processing input: {str(e)}")
            print("Please try again.")

def main():
    parser = argparse.ArgumentParser(description='ASMR.one Downloader')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--search', action='store_true', help='Search mode')
    group.add_argument('--login', action='store_true', help='Login mode')
    
    parser.add_argument('--keyword', help='Search keyword')
    parser.add_argument('--username', help='Username for login')
    parser.add_argument('--password', help='Password for login')
    parser.add_argument('--input-file', default='input.json', help='Input file path')
    parser.add_argument('--config-file', default='config.json', help='Config file path')
    parser.add_argument('--lossless-mode', choices=['Lossless', 'Lossy', 'All'], help='Audio quality mode')
    
    args = parser.parse_args()

    if args.login:
        if not all([args.username, args.password]):
            print("Username and password are required for login")
            return

        api = ASMROneAPI()
        result = api.authenticate(args.username, args.password)
        
        if 'token' not in result:
            print("Login failed:", result.get('error') or result.get('errors', {}).get('msg'))
            return

        config = {}
        if os.path.exists(args.config_file):
            try:
                with open(args.config_file, 'r') as f:
                    config = json.load(f)
            except json.JSONDecodeError:
                pass

        config['token'] = result['token']
        with open(args.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print("Login Successful")
        return

    # Load config
    if not os.path.exists(args.config_file):
        print("Config file not found")
        return

    try:
        with open(args.config_file, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError:
        print("Invalid config file")
        return

    if 'token' not in config:
        print("Token not found in config")
        return

    config_obj = Config(
        token=config['token'],
        lossless_mode=args.lossless_mode or config.get('lossless_mode', 'Lossless'),
        output_pattern=config.get('output_pattern', '<vas>_RJ<id>_<title>_<tags>')
    )

    downloader = Downloader(config_obj)

    if args.search:
        if not args.keyword:
            print("Keyword is required for search")
            return
        # all_works = downloader.api.search_works(args.keyword).get('works', []) single page
        all_works = downloader.api.search_all_pages(args.keyword)
        for i, work in enumerate(all_works):
            print(f"{i+1}. RJ{work['id']} - {work['title']}")
        # save all works to a json file
        with open('all_works.json', 'w', encoding='utf-8') as f:
            json.dump(all_works, f, indent=2, ensure_ascii=False)
        work_ids = display_works_and_get_selection(all_works)
        if not work_ids:
            return
    else:
        if not os.path.exists(args.input_file):
            print("Input file not found")
            return

        try:
            with open(args.input_file, 'r') as f:
                work_ids = json.load(f) # [123456, 234567, RJ345678] list of RJ ids
        except json.JSONDecodeError:
            print("Invalid input file")
            return

    for work_id in work_ids:
        try:
            downloader.download_work(work_id)
        except Exception as e:
            print(f"Error downloading RJ{work_id}: {str(e)}")

if __name__ == "__main__":
    main()