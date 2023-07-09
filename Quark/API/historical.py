import csv
import datetime
import os.path
import pathlib
import time
from collections.abc import Iterable

from PyQuantKit import TradeData

from . import LOGGER
from ..Base import GlobalStatics

ARCHIVE_DIR = rf'{os.path.expanduser("~")}/TradeDataArchive'
DATA_DIR = rf'{os.path.expanduser("~")}/TradeData'
TIME_ZONE = GlobalStatics.TIME_ZONE


def unzip(market_date: datetime.date, ticker: str):
    import py7zr

    archive_path = pathlib.Path(ARCHIVE_DIR, f'{market_date:%Y%m}', f'{market_date:%Y-%m-%d}.7z')
    destination_path = pathlib.Path(DATA_DIR)
    directory_to_extract = f'{market_date:%Y-%m-%d}'
    file_to_extract = f'{ticker.split(".")[0]}.csv'

    if not os.path.isfile(archive_path):
        raise FileNotFoundError(f'{archive_path} not found!')

    os.makedirs(destination_path, exist_ok=True)

    LOGGER.info(f'Unzipping {file_to_extract} from {archive_path} to {destination_path}...')

    with py7zr.SevenZipFile(archive_path, mode='r') as archive:
        archive.extract(targets=[f'{directory_to_extract}/{file_to_extract}'], path=destination_path)

    return 0


def unzip_batch(market_date: datetime.date, ticker_list: Iterable[str]):
    import py7zr

    archive_path = pathlib.Path(ARCHIVE_DIR, f'{market_date:%Y%m}', f'{market_date:%Y-%m-%d}.7z')
    destination_path = pathlib.Path(DATA_DIR)
    directory_to_extract = f'{market_date:%Y-%m-%d}'

    targets = []

    for ticker in ticker_list:
        name = f'{ticker.split(".")[0]}.csv'
        destination = pathlib.Path(DATA_DIR, f'{market_date:%Y-%m-%d}', f'{ticker.split(".")[0]}.csv')

        if os.path.isfile(destination):
            continue

        targets.append(f'{directory_to_extract}/{name}')

    if not os.path.isfile(archive_path):
        raise FileNotFoundError(f'{archive_path} not found!')

    os.makedirs(destination_path, exist_ok=True)

    if not targets:
        return 0

    LOGGER.info(f'Unzipping {len(targets)} names from {archive_path} to {destination_path}...')

    with py7zr.SevenZipFile(archive_path, mode='r') as archive:
        archive.extract(targets=targets, path=destination_path)

    return 0


def load_trade_data(market_date: datetime.date, ticker: str) -> list[TradeData]:
    ts = time.time()
    trade_data_list = []

    file_path = pathlib.Path(DATA_DIR, f'{market_date:%Y-%m-%d}', f'{ticker.split(".")[0]}.csv')

    if not os.path.isfile(file_path):
        try:
            unzip(market_date=market_date, ticker=ticker)
        except FileNotFoundError as _:
            return trade_data_list

    with open(file_path, 'r') as f:
        data_file = csv.DictReader(f)
        for row in data_file:  # type: dict[str, str | float]
            trade_data = TradeData(
                ticker=ticker,
                trade_price=float(row['Price']),
                trade_volume=float(row['Volume']),
                trade_time=datetime.datetime.combine(market_date, datetime.time(*map(int, row['Time'].split(":"))), TIME_ZONE),
                side=row['Type']
            )
            trade_data.additional['sell_order_id'] = int(row['SaleOrderID'])
            trade_data.additional['buy_order_id'] = int(row['BuyOrderID'])
            trade_data_list.append(trade_data)

    LOGGER.info(f'{market_date} {ticker} trade data loaded, {len(trade_data_list):,} entries in {time.time() - ts:.3f}s.')

    return trade_data_list


def loader(market_date: datetime.date, ticker: str, dtype: str):
    if dtype == 'TradeData':
        return load_trade_data(market_date=market_date, ticker=ticker)
    else:
        raise NotImplementedError(f'API.historical does not have a loader function for {dtype}')
