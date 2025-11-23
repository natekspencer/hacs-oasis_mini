[![Release](https://img.shields.io/github/v/release/natekspencer/hacs-oasis_mini?style=for-the-badge)](https://github.com/natekspencer/hacs-oasis_mini/releases)
[![Buy Me A Coffee/Beer](https://img.shields.io/badge/Buy_Me_A_☕/🍺-F16061?style=for-the-badge&logo=ko-fi&logoColor=white&labelColor=grey)](https://ko-fi.com/natekspencer)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

![Downloads](https://img.shields.io/github/downloads/natekspencer/hacs-oasis_mini/total?style=flat-square)
![Latest Downloads](https://img.shields.io/github/downloads/natekspencer/hacs-oasis_mini/latest/total?style=flat-square)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://brands.home-assistant.io/oasis_mini/dark_logo.png">
  <img alt="Oasis Mini logo" src="https://brands.home-assistant.io/oasis_mini/logo.png">
</picture>

# Oasis Control for Home Assistant

Home Assistant integration for Oasis kinetic sand art devices.

# Installation

There are two main ways to install this custom component within your Home Assistant instance:

1. Using HACS (see https://hacs.xyz/ for installation instructions if you do not already have it installed):

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=natekspencer&repository=hacs-oasis_mini&category=integration)

   1. Use the convenient My Home Assistant link above, or, from within Home Assistant, click on the link to **HACS**
   2. Click on **Integrations**
   3. Click on the vertical ellipsis in the top right and select **Custom repositories**
   4. Enter the URL for this repository in the section that says _Add custom repository URL_ and select **Integration** in the _Category_ dropdown list
   5. Click the **ADD** button
   6. Close the _Custom repositories_ window
   7. You should now be able to see the _Oasis Mini_ card on the HACS Integrations page. Click on **INSTALL** and proceed with the installation instructions.
   8. Restart your Home Assistant instance and then proceed to the _Configuration_ section below.

2. Manual Installation:
   1. Download or clone this repository
   2. Copy the contents of the folder **custom_components/oasis_mini** into the same file structure on your Home Assistant instance
      - An easy way to do this is using the [Samba add-on](https://www.home-assistant.io/getting-started/configuration/#editing-configuration-via-sambawindows-networking), but feel free to do so however you want
   3. Restart your Home Assistant instance and then proceed to the _Configuration_ section below.

While the manual installation above seems like less steps, it's important to note that you will not be able to see updates to this custom component unless you are subscribed to the watch list. You will then have to repeat each step in the process. By using HACS, you'll be able to see that an update is available and easily update the custom component.

# Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=oasis_mini)

There is a config flow for this Oasis Control integration. After installing the custom component, use the convenient My Home Assistant link above.

Alternatively:

1. Go to **Configuration**->**Integrations**
2. Click **+ ADD INTEGRATION** to setup a new integration
3. Search for **Oasis Control** and click on it
4. You will be guided through the rest of the setup process via the config flow

# Options

After this integration is set up, you can configure the integration to connect to the Kinetic Oasis cloud API. This will allow pulling in certain details (such as track name and image) that are otherwise not available.

# Actions

The media player entity supports various actions, including managing the playlist queue. You can specify a track by its ID or name. If using a track name, it must match an entry in the [tracks list](custom_components/oasis_mini/pyoasismini/tracks.json). To specify multiple tracks, separate them with commas. An example is below:

```yaml
action: media_player.play_media
target:
  entity_id: media_player.oasis_mini
data:
  media_content_id: 63, Turtle
  media_content_type: track
  enqueue: replace
```

---

## Support Me

I'm not employed by Kinetic Oasis, and provide this custom component purely for your own enjoyment and home automation needs.

If you already own an Oasis device, found this integration useful and want to donate, consider [sponsoring me on GitHub](https://github.com/sponsors/natekspencer) or buying me a coffee ☕ (or beer 🍺) instead by using the link below:

<a href='https://ko-fi.com/Y8Y57F59S' target='_blank'><img height='36' style='border:0px;height:36px;' src='https://storage.ko-fi.com/cdn/kofi1.png?v=3' border='0' alt='Buy Me a Coffee at ko-fi.com' /></a>
