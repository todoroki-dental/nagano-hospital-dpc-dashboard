"""
退院先データの読み込みと前処理モジュール
"""
import pandas as pd
from pathlib import Path
import os


class DischargeDataLoader:
    """退院先データの読み込みと前処理を行うクラス"""

    def __init__(self, file_path: str = "data/ent_nagano.xlsx"):
        # スクリプトの場所を基準にパスを解決
        script_dir = Path(__file__).parent
        self.file_path = script_dir / file_path
        self.raw_data = None
        self.processed_data = None
        self.facilities = None
        self.years = None
        self.destinations = None

    def load_data(self):
        """Excelファイルからデータを読み込む"""
        self.raw_data = pd.read_excel(
            self.file_path,
            sheet_name='退院先',
            header=[0, 1]
        )
        return self

    def process_data(self):
        """データを分析しやすい形式に変換"""
        if self.raw_data is None:
            raise ValueError("データが読み込まれていません。load_data()を先に実行してください。")

        # 施設情報の抽出
        facilities_df = self.raw_data[[('告示番号', 'Unnamed: 0_level_1'),
                                       ('通番', 'Unnamed: 1_level_1'),
                                       ('施設名', 'Unnamed: 2_level_1')]].copy()
        facilities_df.columns = ['告示番号', '通番', '施設名']
        self.facilities = facilities_df

        # 年度と退院先の情報を抽出
        data_columns = [col for col in self.raw_data.columns
                       if col[0] not in ['告示番号', '通番', '施設名']]

        # 年度リスト
        self.years = sorted(list(set([col[0] for col in data_columns])))

        # 退院先リスト（R5年度から取得）
        self.destinations = [col[1] for col in data_columns if col[0] == 'R5']

        # 長形式（long format）に変換
        records = []
        for idx, row in self.raw_data.iterrows():
            facility_name = row[('施設名', 'Unnamed: 2_level_1')]
            kokoku_no = row[('告示番号', 'Unnamed: 0_level_1')]
            tsuban = row[('通番', 'Unnamed: 1_level_1')]

            for year in self.years:
                for dest in self.destinations:
                    value = row[(year, dest)]
                    records.append({
                        '告示番号': kokoku_no,
                        '通番': tsuban,
                        '施設名': facility_name,
                        '年度': year,
                        '退院先': dest,
                        '割合': value
                    })

        self.processed_data = pd.DataFrame(records)
        return self

    def get_facility_list(self):
        """施設名のリストを取得"""
        if self.facilities is None:
            raise ValueError("データが処理されていません。")
        return self.facilities['施設名'].tolist()

    def get_facility_data(self, facility_name: str, year: str = None):
        """特定施設のデータを取得"""
        if self.processed_data is None:
            raise ValueError("データが処理されていません。")

        filtered = self.processed_data[self.processed_data['施設名'] == facility_name]

        if year:
            filtered = filtered[filtered['年度'] == year]

        return filtered

    def get_year_comparison(self, year1: str, year2: str):
        """2年度間の比較データを取得"""
        if self.processed_data is None:
            raise ValueError("データが処理されていません。")

        data1 = self.processed_data[self.processed_data['年度'] == year1].copy()
        data2 = self.processed_data[self.processed_data['年度'] == year2].copy()

        # 差分を計算
        merged = data1.merge(
            data2,
            on=['施設名', '退院先'],
            suffixes=(f'_{year1}', f'_{year2}')
        )
        merged['差分'] = merged[f'割合_{year2}'] - merged[f'割合_{year1}']

        return merged

    def get_facility_comparison(self, facilities: list, destination: str, year: str):
        """複数施設の特定退院先データを比較"""
        if self.processed_data is None:
            raise ValueError("データが処理されていません。")

        filtered = self.processed_data[
            (self.processed_data['施設名'].isin(facilities)) &
            (self.processed_data['退院先'] == destination) &
            (self.processed_data['年度'] == year)
        ]

        return filtered

    def get_summary_stats(self, year: str):
        """年度別の基本統計量を取得"""
        if self.processed_data is None:
            raise ValueError("データが処理されていません。")

        year_data = self.processed_data[self.processed_data['年度'] == year]

        summary = year_data.groupby('退院先')['割合'].agg([
            'mean', 'std', 'min', 'max'
        ]).round(4)

        return summary

    def get_home_discharge_rate(self):
        """「家庭への退院」の合計率を計算（3カテゴリの合計）"""
        if self.processed_data is None:
            raise ValueError("データが処理されていません。")

        home_destinations = [
            '家庭への退院（当院に通院）',
            '家庭への退院（他院への通院）',
            '家庭への退院（その他）'
        ]

        home_data = self.processed_data[
            self.processed_data['退院先'].isin(home_destinations)
        ].copy()

        # 施設・年度ごとに合計
        home_rate = home_data.groupby(['施設名', '年度'])['割合'].sum().reset_index()
        home_rate['退院先'] = '家庭への退院（合計）'

        return home_rate
