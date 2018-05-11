import logging
import urllib.parse
import xml.etree.ElementTree as ET

import requests


class Device(object):

    _PAIRS = (
            ("name", "Name"),
            ("hardware_address", "HardwareAddress"),
            ("protocol", "Protocol"),
            ("model_id", "ModelId"),
            ("manufacturer", "Manufacturer"),
            ("install_code", "InstallCode"),
            ("last_contact", "LastContact"),
            ("connection_status", "ConnectionStatus"),
            ("network_address", "NetworkAddress"))

    @classmethod
    def from_xml(cls, x):
        kwargs = {}
        for attr, tag_name in cls._PAIRS:
            tag = x.find(tag_name)
            if tag is not None:
                kwargs[attr] = tag.text
        return cls(**kwargs)

    def __init__(self, last_contact=None, connection_status=None,
                 network_address=None, hardware_address=None, name=None,
                 protocol=None, manufacturer=None, model_id=None,
                 install_code=None):
        try:
            last_contact = int(last_contact, 16)
        except ValueError:
            pass
        self.last_contact = last_contact
        self.connection_status = connection_status
        self.network_address = network_address
        self.hardware_address = hardware_address
        self.name = name
        self.protocol = protocol
        self.manufacturer = manufacturer
        self.model_id = model_id


class Component(object):

    _PAIRS = (
            ("name", "Name"),
            ("fixed_id", "FixedId"),
            ("hardware_id", "HardwareId"))

    @classmethod
    def from_xml(cls, x):
        kwargs = {}
        for attr, tag_name in cls._PAIRS:
            tag = x.find(tag_name)
            if tag is not None:
                kwargs[attr] = tag.text
        variables = []
        vars_tag = x.find("Variables")
        if vars_tag:
            for var_tag in vars_tag.findall("Variable"):
                variables.append(Variable.from_xml(var_tag))
        kwargs["variables"] = variables
        return cls(**kwargs)

    def __init__(self, hardware_id=None, name=None, fixed_id=None,
                 variables=None):
        self.hardware_id = hardware_id
        self.name = name
        self.fixed_id = fixed_id
        self.variables = variables


class Variable(object):

    _PAIRS = (
            ("name", "Name"),
            ("value", "Value"),
            ("units", "Units"),
            ("description", "Description"))

    @classmethod
    def from_xml(cls, x):
        # This happens in device_details
        text = x.text.strip()
        if text:
            return text
        kwargs = {}
        for attr, tag_name in cls._PAIRS:
            tag = x.find(tag_name)
            if tag is not None:
                kwargs[attr] = tag.text
        return cls(**kwargs)

    def __init__(self, name=None, value=None, units=None, description=None):
        self.name = name
        self.value = value
        self.units = units
        self.description = description


class DeviceComponents(object):

    def __init__(self, device, components):
        self.device = device
        self.components = components


class API(object):

    SCHEME = "http"
    PATH = "/cgi-bin/post_manager"

    def __init__(self, address=None, cloud_id=None, install_code=None):
        assert address is not None or cloud_id is not None
        assert install_code is not None

        if address is None:
            address = "eagle-%s.local" % cloud_id
        self.address = address
        self.cloud_id = cloud_id
        self.install_code = install_code

        self.session = requests.Session()

    def call(self, command):
        data = self.unparse(command)
        logging.debug("-> %r", data)
        u = urllib.parse.urlunparse((
            self.SCHEME, self.address, self.PATH, None, None, None))
        r = self.session.post(
            u, auth=(self.cloud_id, self.install_code),
            headers={"Content-Type": "text/xml"}, data=data)
        logging.debug("<- %r", r.content)
        return r

    def unparse(self, obj):
        return ET.tostring(obj)

    def parse(self, string):
        # Eagle-200 returns unescaped ampersands. Possibly other XML is wrong.
        return ET.fromstring(string.replace(" & ", " &amp; "))

    def do(self, command):
        r = self.call(command)
        r.raise_for_status()
        return self.parse(r.text)

    def _mk_command(self, name, hardware_address=None, variables=None,
                    all=False, refresh=False):
        cmd = ET.Element("Command")
        ET.SubElement(cmd, "Name").text = name
        if hardware_address is not None:
            ET.SubElement(
                ET.SubElement(cmd, "DeviceDetails"),
                "HardwareAddress").text = hardware_address
        if all or variables:
            components = ET.SubElement(cmd, "Components")
            if all:
                ET.SubElement(components, "All").text = "Y"
            else:
                for comp_name, comp_vars in variables.items():
                    comp = ET.SubElement(components, "Component")
                    ET.SubElement(comp, "Name").text = comp_name
                    vars = ET.SubElement(comp, "Variables")
                    if type(comp_vars) is dict:
                        for name, value in comp_vars.items():
                            var = ET.SubElement(vars, "Variable")
                            ET.SubElement(var, "Name").text = name
                            ET.SubElement(var, "Value").text = value
                    else:
                        for name in comp_vars:
                            var = ET.SubElement(vars, "Variable")
                            ET.SubElement(var, "Name").text = name
                            if refresh:
                                ET.SubElement(var, "Refresh").text = "Y"
        return cmd

    def _do(self, name, hardware_address=None, variables=None, all=False,
            refresh=False):
        return self.do(self._mk_command(
            name, hardware_address=hardware_address, variables=variables,
            all=all, refresh=refresh))

    def device_list_xml(self):
        return self._do("device_list")

    def device_list(self):
        x = self.device_list_xml()
        return [Device.from_xml(d) for d in x.findall("Device")]

    def device_details_xml(self, hardware_address):
        return self._do("device_details", hardware_address=hardware_address)

    def device_details(self, hardware_address):
        x = self.device_details_xml(hardware_address)
        return DeviceComponents(
                Device.from_xml(x.find("DeviceDetails")),
                [Component.from_xml(tag)
                    for tag in x.find("Components").findall("Component")])

    def device_query_xml(self, hardware_address, variables=None, all=False,
                     refresh=False):
        return self._do(
            "device_query", hardware_address=hardware_address,
            variables=variables, all=all, refresh=refresh)

    def device_query(self, hardware_address, variables=None, all=False,
                     refresh=False):
        x = self.device_query_xml(
                hardware_address, variables=variables, all=all,
                refresh=refresh)
        return DeviceComponents(
                Device.from_xml(x.find("DeviceDetails")),
                [Component.from_xml(tag)
                    for tag in x.find("Components").findall("Component")])

    def device_control_xml(self, hardware_address, variables=None):
        return self._do("device_control", variables=variables)
