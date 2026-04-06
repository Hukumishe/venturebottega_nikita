import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup
from loguru import logger

from engine.core.config import settings


class DagospiaFetcher:
    BASE_URL = "https://www.dagospia.com"
    COMPACTED_FILENAME = "dagospia_compacted.json"
    LATEST_FILENAME = "dagospia_latest.json"

    def __init__(
        self,
        save_to_files: bool = True,
        output_path: Optional[Path] = None,
        timeout: int = 20,
    ):
        self.save_to_files = save_to_files
        self.output_path = output_path or Path(settings.DAGOSPIA_DATA_PATH)
        self.timeout = timeout

        if self.save_to_files:
            self.output_path.mkdir(parents=True, exist_ok=True)

    @property
    def compacted_path(self) -> Path:
        return self.output_path / self.COMPACTED_FILENAME

    @property
    def latest_path(self) -> Path:
        return self.output_path / self.LATEST_FILENAME

    def refresh(self) -> Dict[str, int]:
        latest_df = self.scrape()
        existing_df = self._load_existing_dataset()
        old_count = len(existing_df)
        latest_count = len(latest_df)

        combined = pd.concat([existing_df, latest_df], ignore_index=True)
        if not combined.empty:
            combined = combined.drop_duplicates().reset_index(drop=True)

        compacted_count = len(combined)
        removed_files = 0
        if self.save_to_files:
            self._write_records_json(self.latest_path, latest_df)
            self._write_records_json(self.compacted_path, combined)
            removed_files = self._cleanup_redundant_json_files()

        return {
            "existing_records": old_count,
            "latest_records": latest_count,
            "compacted_records": compacted_count,
            "removed_files": removed_files,
        }

    def scrape(self) -> pd.DataFrame:
        logger.info("Fetching Dagospia homepage...")
        response = requests.get(self.BASE_URL, timeout=self.timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        articles = soup.find_all("article")

        rows: List[Dict[str, str]] = []
        for article in articles:
            rows.append(self._parse_article(article))

        df = pd.DataFrame(rows, columns=["excerpt", "timestmp", "keywords", "detail"]).fillna("N/A")
        logger.info(f"Scraped {len(df)} rows from Dagospia homepage")
        return df

    def _parse_article(self, article) -> Dict[str, str]:
        excerpt = (
            excerpt_node.get_text(strip=True)
            if (excerpt_node := article.find("div", class_="excerpt"))
            else "N/A"
        )
        timestamp = time_node.get_text(strip=True) if (time_node := article.find("time")) else "N/A"
        keywords = image_node.get("alt", "N/A") if (image_node := article.find("img")) else "N/A"
        detail = "N/A"
        if link_node := article.find("a"):
            href = link_node.get("href")
            if href:
                detail = href if href.startswith("http") else f"{self.BASE_URL}{href}"

        return {
            "excerpt": excerpt,
            "timestmp": timestamp,
            "keywords": keywords,
            "detail": detail,
        }

    def _load_existing_dataset(self) -> pd.DataFrame:
        if not self.output_path.exists():
            return pd.DataFrame(columns=["excerpt", "timestmp", "keywords", "detail"])

        json_files = sorted(self.output_path.glob("*.json"))
        if not json_files:
            return pd.DataFrame(columns=["excerpt", "timestmp", "keywords", "detail"])

        dataframes: List[pd.DataFrame] = []
        for file_path in json_files:
            df = self._load_dataframe_from_json(file_path)
            if df.empty:
                continue
            expected_cols = ["excerpt", "timestmp", "keywords", "detail"]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = "N/A"
            dataframes.append(df[expected_cols])

        if not dataframes:
            return pd.DataFrame(columns=["excerpt", "timestmp", "keywords", "detail"])

        merged = pd.concat(dataframes, ignore_index=True).fillna("N/A")
        logger.info(f"Loaded {len(merged)} existing Dagospia rows from {len(dataframes)} JSON files")
        return merged

    def _load_dataframe_from_json(self, file_path: Path) -> pd.DataFrame:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            logger.warning(f"Skipping unreadable JSON file {file_path.name}: {e}")
            return pd.DataFrame()

        try:
            if isinstance(raw, list):
                return pd.DataFrame(raw)
            if isinstance(raw, dict):
                if raw and all(isinstance(v, dict) for v in raw.values()):
                    return pd.DataFrame(raw)
                return pd.DataFrame(raw)
        except Exception as e:
            logger.warning(f"Failed parsing JSON shape in {file_path.name}: {e}")
            return pd.DataFrame()

        logger.warning(f"Unsupported JSON structure in {file_path.name}, skipping")
        return pd.DataFrame()

    def _write_records_json(self, file_path: Path, df: pd.DataFrame) -> None:
        tmp_path = file_path.with_suffix(f"{file_path.suffix}.tmp")
        records = df.to_dict(orient="records")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        tmp_path.replace(file_path)

    def _cleanup_redundant_json_files(self) -> int:
        if not self.output_path.exists():
            return 0

        keep_names = {self.COMPACTED_FILENAME, self.LATEST_FILENAME}
        removed = 0
        for file_path in self.output_path.glob("*.json"):
            if file_path.name in keep_names:
                continue
            file_path.unlink(missing_ok=True)
            removed += 1
        return removed


def main() -> int:
    fetcher = DagospiaFetcher(save_to_files=True)
    result = fetcher.refresh()
    logger.info(f"Dagospia refresh completed: latest={result['latest_records']}, "
                f"compacted={result['compacted_records']}, removed_files={result['removed_files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
