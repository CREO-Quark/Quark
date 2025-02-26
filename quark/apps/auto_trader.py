import datetime
import enum
import json
import time
import tkinter
from threading import Event
from tkinter import ttk
from typing import Literal, Any

import numpy as np
import pandas as pd
import requests
from algo_engine.apps.sim_input.client import AutoWorkClient, Action
from algo_engine.apps.sim_input.sim_keyboard import simulate_keypress
from algo_engine.apps.sim_input.sim_mouse import move_mouse, click_mouse

from quark.apps.redis import Client
from quark.base import GlobalStatics, LOGGER

CONFIG = GlobalStatics.CONFIG
LOGGER = LOGGER.getChild('AutoTrader')
__version__ = '1.0.1'
PRIVATE_KEY = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIGh2DP57YyvNsDbvXZKwttDzdzKXM/fLew8jC+VKqiVmoAoGCCqGSM49
AwEHoUQDQgAEHiL9KneP15sateLTz3XW6tueWBIchVPVkwLIRIsXR+bcXRhe0Sel
o+pk6c/T4udLQm+Gne5sMSqX9Sdzi7vD5A==
-----END EC PRIVATE KEY-----"""


class TradeSignal(enum.IntEnum):
    short_open = 4
    long_close = 3
    no_action = 0
    long_open = 1
    short_close = 2


class AutoTrader(AutoWorkClient):
    def __init__(self, **kwargs):
        super().__init__(
            title=f'AutoTrader {__version__}',
            **kwargs
        )

        self.redis_client = Client(
            ssh_host=kwargs.get('ssh_host'),
            ssh_port=kwargs.get('ssh_port'),
            ssh_username=kwargs.get('ssh_username'),
            ssh_password=kwargs.get('ssh_password'),
            ssh_pkey=kwargs.get('ssh_pkey'),
            redis_host=kwargs.get('redis_host', CONFIG.get_config('Strategy.Redis.HOST', default='localhost')),
            redis_port=kwargs.get('redis_port', CONFIG.get_config('Strategy.Redis.PORT', default=6379)),
            redis_password=kwargs.get('redis_password', CONFIG.get_config('Strategy.Redis.PASSWORD', default=None))
        )

        self.redis_client.start()
        self.private_key, self.public_key = self.load_key(PRIVATE_KEY) if PRIVATE_KEY else self.generate_keypair()
        self.signal_event = Event()
        self.signal_lock = Event()
        self.signal = 0

        self.slack_webhook = "https://hooks.slack.com/services/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"

    def render_layout(self):
        super().render_layout()

        # Grid(0, 3) with rowspan=2: Create a frame for the mode selector
        mode_frame = self.layout['mode_frame'] = ttk.Frame(self.root)
        mode_frame.grid(row=0, column=2, rowspan=2, padx=10, pady=10, sticky="n")

        # Add a label inside the mode frame
        mode_label = ttk.Label(mode_frame, text="Mode:")
        mode_label.grid(row=0, column=0, pady=(0, 5))

        # Create a StringVar to hold the current mode value
        mode_var = self.layout['mode_var'] = tkinter.StringVar(value="Disabled")

        # Add radio buttons inside the mode frame
        modes = ["Disabled", "Open Position", "Close Position"]
        for i, mode in enumerate(modes, start=1):
            radio_button = ttk.Radiobutton(
                mode_frame,
                text=mode,
                value=mode,
                variable=mode_var,
                command=self.on_mode_change  # Callback for when the mode changes
            )
            radio_button.grid(row=i, column=0, sticky="w", padx=5, pady=2)
        self.layout['action_table'].grid(row=2, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

    def on_mode_change(self):
        """Callback function for mode changes."""
        selected_mode = self.layout['mode_var'].get()
        LOGGER.info(f"Mode changed to: {selected_mode}")
        # Add logic to update the program's behavior based on the mode.

    def run(self):
        self.redis_client.subscribe(topic='signal', callback=self.on_signal)

        self.register_action(action=self.long_open_action(), signal=TradeSignal.long_open)
        self.register_action(action=self.short_open_action(), signal=TradeSignal.short_open)

        self.root.mainloop()

    def listen_signal(self) -> int:
        LOGGER.info("Waiting for a valid trade signal...")
        self.signal_event.wait()  # Block until the event is set
        LOGGER.info(f"Processing valid signal: {self.signal}")
        signal_value = self.signal
        self.signal = None  # Reset the signal
        self.signal_event.clear()  # Reset the event
        self.signal_lock.set()
        return signal_value

    def build_payload(self, side: int, data_dict: dict) -> dict:
        price = data_dict['market_price']

        if side > 0:
            header = f":large_green_square: :chart_with_upwards_trend: [{datetime.datetime.fromtimestamp(data_dict['timestamp']):%H:%M:%S}] <{data_dict['ticker']}> Long Signal"
        elif side < 0:
            header = f":large_red_square: :chart_with_downwards_trend: [{datetime.datetime.fromtimestamp(data_dict['timestamp']):%H:%M:%S}] <{data_dict['ticker']}> Short Signal"
        else:
            raise Exception(f"Invalid side: {side}!")

        pred_df = self.prediction_to_df({k: v for k, v in data_dict.items() if k not in ['ticker', 'timestamp', 'market_price', 'action', 'signal']})
        df_formatted = pred_df.map(lambda x: x if isinstance(x, str) else f"{x:.2%}" if pd.notnull(x) else "-")
        table_md = f"```{df_formatted.to_string()}```"
        message_payload = {"blocks": []}

        # Part 1: The header
        message_payload["blocks"].extend([
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header,
                    "emoji": True
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Signal price: {price:.2f}"
                }
            }
        ])
        # Part 2: The body
        message_payload["blocks"].extend([
            # Divider line
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Prediction:\n" + table_md
                }
            }
        ])

        signature = self.sign(payload=message_payload, private_key=self.private_key)

        # Part 3: Digital signature
        message_payload["blocks"].extend([
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Message signed by Bolun.*"
                }
            },
            # Button for expand/collapse interaction
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "Show Signature"
                        },
                        "confirm": {
                            "title": {
                                "type": "plain_text",
                                "text": "Digital Signature:"
                            },
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{signature}"
                            }
                        },
                        "style": "primary",
                        "value": "digital_signature"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "Show Public Key"
                        },
                        "confirm": {
                            "title": {
                                "type": "plain_text",
                                "text": "Public Key:"
                            },
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{self.dump_public_key(self.public_key)}"
                            }
                        },
                        "style": "primary",
                        "value": "public_key"
                    },
                ]
            }
        ])

        return message_payload

    def notify(self, payload: dict[str, Any]) -> None:
        # Send the message
        response = requests.post(
            self.slack_webhook,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload)
        )

        # Check the response
        if response.status_code == 200:
            LOGGER.debug("Message sent successfully!")
        else:
            LOGGER.info(f"Failed to send message. Status code: {response.status_code}, Response: {response.text}")

    def on_signal(self, msg: str | bytes):
        json_dict = json.loads(msg)
        LOGGER.info(f'on_msg {json_dict}')

        sig = self.trade_decision(data=json_dict)
        self.signal = sig

        if not sig:
            return

        self.signal_event.set()
        self.signal_lock.wait()
        self.signal_lock.clear()

    @classmethod
    def prediction_to_df(cls, prediction: dict[str, float]) -> pd.DataFrame:
        data = {}

        for key, value in prediction.items():
            if key.endswith('.upper_bound'):
                pred_topic = key.rstrip('.upper_bound')
                pred_type = 'upper_bound'
            elif key.endswith('.lower_bound'):
                pred_topic = key.rstrip('.lower_bound')
                pred_type = 'lower_bound'
            else:
                pred_topic = key
                pred_type = 'value'

            # Initialize the base key in data if not present
            if pred_topic not in data:
                data[pred_topic] = {'value': np.nan, 'lower_bound': np.nan, 'upper_bound': np.nan}

            # Assign the value to the correct column (value, lower_bound, upper_bound)
            data[pred_topic][pred_type] = value

        # Convert the dictionary to a DataFrame
        df = pd.DataFrame.from_dict(data, orient='index')
        return df

    def trade_decision(self, data: dict) -> Literal[-1, 0, 1]:
        if data['state_3.lower_bound'] > 0:
            payload = self.build_payload(side=1, data_dict=data)
            self.notify(payload=payload)
            return 1

        if data['state_3.upper_bound'] < 0:
            payload = self.build_payload(side=-1, data_dict=data)
            self.notify(payload=payload)
            return -1

        return 0

    def long_open_action(self) -> Action:
        launch_long_order_pos = 450, 925

        action = Action(name='Launch Long Open Order')
        action.append(name='move to <Button>(Open Long)', action=move_mouse, args=launch_long_order_pos, comments='The cursor should be landed at the [Red_Button]("买多")')
        action.append(name='click <Button>(Open Long)', action=click_mouse)
        action.append(name='await confirmation...', action=time.sleep, args=(0.1,))
        action.append(name='confirm', action=simulate_keypress, args=('\n',))
        action.append(name='release control', action=self.release_control)

        return action

    def short_open_action(self) -> Action:
        launch_short_order_pos = 560, 925

        action = Action(name='Launch Short Open Order')
        action.append(name='move to <Button>(Open Short)', action=move_mouse, args=launch_short_order_pos, comments='The cursor should be landed at the [Green_Button]("卖空")')
        action.append(name='click <Button>(Open Short)', action=click_mouse)
        action.append(name='await confirmation...', action=time.sleep, args=(0.1,))
        action.append(name='confirm', action=simulate_keypress, args=('\n',))
        action.append(name='release control', action=self.release_control)

        return action

    def long_close_action(self) -> Action:
        raise NotImplementedError

    def short_close_action(self) -> Action:
        raise NotImplementedError

    @classmethod
    def generate_keypair(cls):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend

        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        return private_key, private_key.public_key()

    @classmethod
    def load_key(cls, key_str: str):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend

        key_bytes = key_str.encode('utf-8')
        private_key = serialization.load_pem_private_key(
            key_bytes,
            password=None,
            backend=default_backend()
        )
        return private_key, private_key.public_key()

    @classmethod
    def dump_key(cls, private_key) -> str:
        from cryptography.hazmat.primitives import serialization

        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        return private_key_pem.decode('utf-8')

    @classmethod
    def dump_public_key(cls, public_key) -> str:
        from cryptography.hazmat.primitives import serialization

        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )
        return public_key_pem.decode('utf-8')

    @classmethod
    def sign(cls, payload: dict, private_key) -> str:
        import json
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        # Serialize payload to JSON string
        assert 'signature' not in payload

        payload_json = json.dumps(payload, separators=(',', ':'))

        # Hash the payload using SHA-256
        hasher = hashes.Hash(hashes.SHA256())
        hasher.update(payload_json.encode('utf-8'))
        hashed_payload = hasher.finalize()

        # Sign the hashed payload with the ECDSA private key
        signature = private_key.sign(
            hashed_payload,
            ec.ECDSA(hashes.SHA256())
        )

        # payload['signature'] = signature
        return signature.hex()  # Return as a hex string

    @classmethod
    def verify(cls, message: dict, signature: str, public_key) -> bool:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes

        # Serialize the message to JSON string
        message_json = json.dumps(message, separators=(',', ':'))

        # Hash the message using SHA-256
        hasher = hashes.Hash(hashes.SHA256())
        hasher.update(message_json.encode('utf-8'))
        hashed_message = hasher.finalize()

        # Convert the signature from hex back to bytes
        signature_bytes = bytes.fromhex(signature)

        try:
            # Verify the signature using the ECDSA public key
            public_key.verify(
                signature_bytes,
                hashed_message,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except:
            return False


def main():
    _at = AutoTrader(
        ssh_host='192.168.2.25',
        ssh_username='airflow',
        ssh_port=19048,
        ssh_pkey=r"C:\Users\Bolun\.ssh\airflow_ed25519.pem",
        redis_host='10.72.97.95',
        redis_port=6379,
        redis_password='8t4B!P9a8vTAnPFe',
    )

    _at.run()


if __name__ == '__main__':
    main()
