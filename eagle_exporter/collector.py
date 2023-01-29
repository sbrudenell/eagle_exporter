import prometheus_client.core


class Eagle200Collector(object):

    _COUNTER_METRICS = set((
        "zigbee:CurrentSummationDelivered",
        "zigbee:CurrentSummationReceived"))

    def __init__(self, api):
        self.api = api
        self._prefix = "eagle_"

    def make_metric(self, _is_counter, _name, _documentation, _value,
                    **_labels):
        if _is_counter:
            cls = prometheus_client.core.CounterMetricFamily
        else:
            cls = prometheus_client.core.GaugeMetricFamily
        label_names = list(_labels.keys())
        metric = cls(
            _name, _documentation or "No Documentation", labels=label_names)
        metric.add_metric([str(_labels[k]) for k in label_names], _value)
        return metric

    def collect(self):
        metrics = []
        for device in self.api.device_list():
            qdata = self.api.device_query(device.hardware_address, all=True)
            last_contact = self.make_metric(
                True, self._prefix + "device_last_contact",
                "Time the EAGLE last had contact with the device",
                qdata.device.last_contact, 
                name=qdata.device.name,
                hardware_address=qdata.device.hardware_address)
            metrics.append(last_contact)
            state = self.make_metric(
                False, self._prefix + "device_state",
                "State of the EAGLE",
                1,
                name=qdata.device.name,
                hardware_address=qdata.device.hardware_address,
                connection_status=qdata.device.connection_status)
            metrics.append(state)
            for component in qdata.components:
                for var in component.variables:
                    if not var.value:
                        continue
                    try:
                        value = float(var.value)
                    except ValueError:
                        continue
                    name = self._prefix + var.name
                    docs = var.description
                    if var.units:
                        docs += " (Units: %s)" % var.units
                    metric = self.make_metric(
                        var.name in self._COUNTER_METRICS,
                        name,
                        docs,
                        value,
                        device_name=device.name or qdata.device.name,
                        device_hardware_address=device.hardware_address,
                        component_name=component.name,
                        component_fixed_id=component.fixed_id,
                        component_hardware_id=component.hardware_id)
                    metrics.append(metric)
        return metrics
