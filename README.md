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
  To install, place the <code>custom_components</code> folder into your Home Assistant configuration directory. <br>
  Alternatively, you can install via <a href="https://hacs.xyz/">HACS</a>.
</p>
<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=ShonP40&repository=Tuya-BLE&category=integration">
    <img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="HACS">
  </a>
</p>

<h2 align="center">Configuration & Setup</h2>
<p align="center">
  Once installed, you will need to manually create a `devices.json` file in `config/tuya_local_ble` with the following format:

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
      <td>Smart Locks<br>(ms)</td>
      <td>Smart Lock</td>
      <td>'ludzroix', 'isk2p555'</td>
      <td>Allows lock/unlock control and status monitoring.</td>
    </tr>
    <tr>
      <td>Smart Locks<br>(jtmspro)</td>
      <td>Smart Lock</td>
      <td>'rlyxv7pe'</td>
      <td>Allows lock/unlock control and status monitoring.</td>
    </tr>
    <tr>
      <td>Smart Locks<br>(jtmspro)</td>
      <td>Raykube A1 Ultra / A1 Pro Max</td>
      <td>'hc7n0urm'</td>
      <td>Experimental TuyaOS FD50 local BLE remote unlock support. See <a href="docs/raykube-a1-ultra-fd50.md">protocol notes</a>.</td>
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
      <td>Irrigation Computer<br>(ggq)</td>
      <td>Irrigation Computer</td>
      <td>'6pahkcau'</td>
      <td>Automates and schedules garden or lawn watering.</td>
    </tr>
  </tbody>
</table>

<h2 align="center">Additional Note</h2>
<p align="center">
  This integration is a work-in-progress. More devices, categories, and features are planned.
</p>

<h2 align="center">Contributing</h2>
<p align="center">
  Contributions are welcome! If you encounter issues or have suggestions for enhancements, please open an issue or create a pull request.
</p>

<h2 align="center">License</h2>
<p align="center">
  This project is licensed under the MIT License. <br> See the <a href="LICENSE">LICENSE</a> file for details.
</p>