<h1 align="center"><br>Tuya BLE</h1>

<p align="center">
  <img src="https://img.shields.io/github/license/ShonP40/Tuya-BLE?style=flat-square" alt="License">
  <img src="https://img.shields.io/github/stars/ShonP40/Tuya-BLE?style=flat-square" alt="Stars">
  <img src="https://img.shields.io/github/forks/ShonP40/Tuya-BLE?style=flat-square" alt="Forks">
</p>

<h2 align="center">Overview</h2>
<p align="center">
  This integration allows you to integrate and control Tuya BLE (Bluetooth Low Energy) devices directly within Home Assistant, <br>
  enabling local operations without relying on remote cloud services for core functionality.
</p>
<p align="center">
  Inspired by and derived from the code of: <br>
  💐 <a href="https://github.com/PlusPlus-ua/ha_tuya_ble">@PlusPlus-u</a> 💐<br>
  💐 <a href="https://github.com/redphx/poc-tuya-ble-fingerbot">@redphx 💐</a><br>
  💐 <a href="https://github.com/SupaHotMoj0/tuya_ble">@SupaHotMoj0 💐</a><br>
  💐 <a href="https://github.com/dmickeyus">@dmickeyus 💐</a>
</p>

<h2 align="center">Features</h2>
<p align="center">
  • Automatic or manual discovery of supported Tuya BLE devices <br>
  • Local control and status reporting <br>
  • Support for multiple device categories and models <br>
  • No cloud round-trip for commands once the device credentials are obtained
</p>

<h2 align="center">Installation</h2>
<p align="center">
  To install, add this repository to your Home Assistant marketplace & install the integration.
</p>
<p align="center">
  <a href="https://my.home-assistant.io/redirect/marketplace_repository/?owner=ShonP40&repository=Tuya-BLE&category=integration">
    <img src="https://my.home-assistant.io/badges/marketplace_repository.svg" alt="HACS">
  </a>
</p>

<h2 align="center">Configuration & Setup</h2>
<p align="center">
  Once installed, add the integration from Settings → Devices & Services → Add Integration → Tuya Local BLE
  (or accept the automatic Bluetooth discovery notification when a supported device is nearby). Pick your device
  from the list, and if it isn't already registered, you'll be prompted right there in the UI for its credentials:
  UUID, local key, device ID, category, and product ID (device name, product name, product model and BLE unlock
  check are optional). You can obtain these using <a href="https://github.com/jasonacox/tinytuya">TinyTuya</a> against your
  Tuya cloud account — no need to unpair the device from the Tuya app first.
</p>
<p align="center">
  <b>Legacy / bulk import:</b> if you'd rather provision several devices at once outside the UI, you can still
  manually create a `devices.json` file in `config/tuya_local_ble`, keyed by the device's BLE MAC address:

  ```json
  {
    "XX:XX:XX:XX:XX:XX": {
    "address": "XX:XX:XX:XX:XX:XX",
    "uuid": "<device UUID>",
    "local_key": "<device local key>",
    "device_id": "<device ID>",
    "category": "jtmspro",
    "product_id": "rlyxv7pe",
    "device_name": "<name>> Lock",
    "product_model": "AT1",
    "product_name": "Smart lock"
    }
  }
  ```

  You can obtain the device MAC address, UUID, local key, device ID, and product ID using [TinyTuya](https://github.com/jasonacox/tinytuya).

  Raykube A1 Ultra / A1 Pro Max (`hc7n0urm`), CTL20H SmartLock (`y2yaegze`) and HTMCKM5 B5 (`nglqaett`) devices require the device-specific `ble_unlock_check` value in `devices.json` for remote unlock. Without it, remote unlock will fail before a BLE command is built. See [`docs/raykube-a1-ultra-fd50.md`](docs/raykube-a1-ultra-fd50.md) and [`docs/ctl20h-smartlock-fd50.md`](docs/ctl20h-smartlock-fd50.md) for the existing FD50 lock setup examples.

  The `j3n6jw2y` lock has no lock/unlock command DP; Home Assistant lock/unlock toggles passage mode (dp 78 `special_control`) off/on. No `ble_unlock_check` value is needed.

  HL Knob-2 (`ikphogdj`) devices also require the device-specific `ble_unlock_check` value in `devices.json` for remote unlock. Without it, locking may work but unlocking will fail before a BLE command is built. See [`docs/hl-knob-2-ikphogdj.md`](docs/hl-knob-2-ikphogdj.md).
</p>

<h2 align="center">Supported Devices</h2>
<table align="center">
  <thead>
    <tr>
      <th>Category (ID)</th>
      <th>Device Name</th>
      <th>Product ID(s)</th>
      <th>Description / Features</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="5">Fingerbots<br>(szjqr)</td>
      <td>Fingerbot</td>
      <td>'ltak7e1p', 'y6kttvd6', 'yrnk7mnn', 'nvr2rocq', 'bnt7wajf', 'rvdceqjh', '5xhbk964'</td>
      <td>The original CR2 battery-powered device.</td>
    </tr>
    <tr>
      <td>Adaprox Fingerbot</td>
      <td>'y6kttvd6'</td>
      <td>Similar to the original Fingerbot, featuring a built-in battery with USB-C charging.</td>
    </tr>
    <tr>
      <td>Fingerbot Plus</td>
      <td>'blliqpsj', 'ndvkgsrm', 'yiihr7zh', 'neq16kgd'</td>
      <td>Enhanced Fingerbot with a sensor button for manual control.</td>
    </tr>
    <tr>
      <td>CubeTouch 1s</td>
      <td>'3yqdo5yt'</td>
      <td>Built-in battery and USB-C charging.</td>
    </tr>
    <tr>
      <td>CubeTouch II</td>
      <td>'xhf790if'</td>
      <td>Built-in battery and USB-C charging.</td>
    </tr>
    <tr>
      <td rowspan="2">Temperature &amp; Humidity Sensors<br>(wsdcg)</td>
      <td>Soil Moisture Sensor</td>
      <td>'ojzlzzsw'</td>
      <td>Monitors soil moisture levels.</td>
    </tr>
    <tr>
      <td>Temperature Humidity Sensor</td>
      <td>'jm6iasmb'</td>
      <td>Monitors Temperature & Humidity levels.</td>
    </tr>
    <tr>
      <td>CO2 Sensors<br>(co2bj)</td>
      <td>CO2 Detector</td>
      <td>'59s19z5m'</td>
      <td>Measures CO2 concentrations.</td>
    </tr>
    <tr>
      <td>Luminance sensors<br>(ldcg)</td>
      <td>RV CO And Propane Gas Alarm</td>
      <td>'poaanotz'</td>
      <td>Measures CO and Propane concentrations.</td>
    </tr>
    <tr>
      <td>Smart Locks<br>(ms)</td>
      <td>Smart Lock</td>
      <td>'ludzroix', 'isk2p555'</td>
      <td>Allows lock/unlock control and status monitoring.</td>
    </tr>
    <tr>
      <td rowspan="2">Smart Locks<br>(jtmspro)</td>
      <td>Raykube A1 Ultra / A1 Pro Max / CTL20H SmartLock / HL Knob-2 / MYPIN HS0358 / j3n6jw2y Smart Lock / EC-LOCK (BAFUWEIY)</td>
      <td>'rlyxv7pe', 'hc7n0urm', 'y2yaegze', 'ikphogdj', 'c6hfl8bt', 'j3n6jw2y', 'vsf3sqif'</td>
      <td>Allows lock/unlock control and status monitoring.</td>
    </tr>
    <tr>
      <td>HTMCKM5 B5</td>
      <td>'nglqaett'</td>
      <td>Supports remote unlock, lock status monitoring, battery state, beep volume, and auto-lock settings. Remote lock is not exposed because this model has no manual_lock (DP46).</td>
    </tr>
    <tr>
      <td>Climate<br>(wk)</td>
      <td>Thermostatic Radiator Valve</td>
      <td>'drlajpqc', 'nhj2j7su'</td>
      <td>Controls and regulates radiator heating.</td>
    </tr>
    <tr>
      <td>Smart Water Bottle<br>(znhsb)</td>
      <td>Smart Water Bottle</td>
      <td>'cdlandip'</td>
      <td>Monitors water intake and temperature.</td>
    </tr>
    <tr>
      <td rowspan="2">Irrigation Computer<br>(ggq)</td>
      <td>Irrigation Computer</td>
      <td>'6pahkcau'</td>
      <td>Automates and schedules garden or lawn watering.</td>
    </tr>
    <tr>
      <td>Hoselink Dual-Outlet Tap Timer</td>
      <td>'qycalacn'</td>
      <td>Two independent outlets: switches, countdowns, normal/cyclic schedules, weather delays, and usage/battery/status/fault sensors. See the <a href="docs/hoselink-tap-timer.md#watering-schedules">schedule actions guide</a>.</td>
    </tr>
  </tbody>
</table>

<h2 align="center">Contributing</h2>
<p align="center">
  Contributions are welcome! If you encounter issues or have suggestions for enhancements, please open an issue or create a pull request.
</p>

<h2 align="center">License</h2>
<p align="center">
  This project is licensed under the MIT License. <br> See the <a href="LICENSE">LICENSE</a> file for details.
</p>
