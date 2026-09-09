# Capturing and validating the protocol

The implemented protocol is described in [PROTOCOL.md](PROTOCOL.md). It comes from labeled Windows MythCool captures. The included `tests/fixtures/usb-events.csv` contains only extracted HID events needed by regression tests, not complete bus captures.

## Linux capture helper

Install `tshark` (which supplies `dumpcap`) using your distribution's packages, then:

```sh
python3 tools/capture-mythcool.py --list
python3 tools/capture-mythcool.py --seconds 30 --action rgb-brightness-255-to-127
```

The helper requires exactly one candidate, or an explicitly verified sysfs port passed with `--device`. It asks sudo to load usbmon and capture; it never sends device commands. It filters saved packets by the selected USB bus/address. Do not reconnect the device during capture. Record one change at a time and note the visible result. Run the analyzer with `python3 tools/analyze-mythcool.py --help` for accepted inputs.

MythCool must detect the cooler before its controls can generate meaningful traffic. Bottles/Wine compatibility is not guaranteed; permissions alone do not establish working HID enumeration. Windows captures can be made with USBPcap/Wireshark, selecting the cooler's controller and retaining only its traffic before sharing.

## Physical validation still needed

Close other controllers. Confirm the supported USB identity and descriptor, then check one reversible lighting change and verify the fan state is preserved. Separately check general power and explicit takeover from the physical knob. Validate the percentage-to-RPM endpoints against the cooler display before relying on full-range calibration. A matching USB readback confirms protocol state, not LED appearance or tachometer speed.

Never publish unfiltered USB captures, bottle backups or private machine logs. The optional Bottles/Soda helpers are diagnostics and are not required to run Llano Control.
