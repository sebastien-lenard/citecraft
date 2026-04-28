import csv
import os
from config_loader import OUTPUT_DIR
from citation_parser import CitationParser
from reference_fetcher import ReferenceFetcher

class BibliographyManager:
    """
    Manages the workflow: loading files, triggering extraction, 
    and exporting the resulting bibliography to CSV.
    """
    def __init__(self, input_file):
        self.input_file = input_file
        self.parser = CitationParser()
        self.fetcher = ReferenceFetcher()
        self.citations = []

    def build_bibliography(self, keywords=None):
        """
        Orchestration: For each citation, fetch candidates from API.
        Returns a list of dictionaries ready for CSV export.
        """
        full_results = []
        print(f"Starting API lookups for {len(self.citations)} unique citations...")
        
        for cite in self.citations:
            author = cite['author']
            year = cite['year']
            
            print(f"  Fetching: {author} ({year})...")
            candidates = self.fetcher.fetch_apa_candidates(author, year, keywords=keywords)
            
            if not candidates:
                full_results.append({
                    'Author': author,
                    'Year': year,
                    'Score': 0,
                    'Type': 'N/A',
                    'APA_Reference': 'NOT FOUND',
                    'DOI': 'N/A'
                })
            else:
                for cand in candidates:
                    full_results.append({
                        'Author': author,
                        'Year': year,
                        'Score': cand.get('score', 0),
                        'Type': cand.get('type', 'unknown'),
                        'APA_Reference': cand.get('apa', ''),
                        'DOI': cand.get('doi', '')
                    })
        
        # Sort results: Author (A-Z), Year (A-Z), then Score (Descending)
        full_results.sort(key=lambda x: (x['Author'], x['Year'], -x['Score']))
        return full_results

    def load_and_parse(self, start_line=None, end_line=None):
        """Reads file and extracts unique citations."""
        if not os.path.exists(self.input_file):
            print(f"Error: File '{self.input_file}' not found.")
            return

        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Logic for 'Test Mode' range (lines n to p)
            if start_line is not None and end_line is not None:
                start_idx = max(0, start_line - 1)
                end_idx = min(len(lines), end_line)
                content = "".join(lines[start_idx:end_idx])
            else:
                content = "".join(lines)

            self.citations = self.parser.extract_citations(content)
            self.citations.sort(key=lambda x: (x['author'], x['year']))
            
        except Exception as e:
            print(f"An error occurred during parsing: {e}")

    def export_to_csv(self, filename, api_results=None, target_dir=None):
        """
        Generates the CSV file. 
        If api_results is None, it exports the 'PENDING' list (for legacy tests).
        If api_results is provided, it exports the enriched data.
        """
        base_dir = target_dir if target_dir else OUTPUT_DIR
        output_path = os.path.join(base_dir, filename)
        
        # New fieldnames including Score and Type
        fieldnames = ['Author', 'Year', 'Score', 'Type', 'APA_Reference', 'DOI']
        
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                if api_results:
                    # Exporting results from build_bibliography()
                    writer.writerows(api_results)
                else:
                    # Fallback for unit tests that only check extraction
                    for cit in self.citations:
                        row = {
                            'Author': cit['author'],
                            'Year': cit['year'],
                            'Score': 0,
                            'Type': 'PENDING',
                            'APA_Reference': 'PENDING_API',
                            'DOI': ''
                        }
                        writer.writerow(row)
            print(f"CSV successfully written to: {output_path}")
            
        except IOError as e:
            print(f"Error writing CSV file: {e}")