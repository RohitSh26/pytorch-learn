# azure_monitor_metrics.py

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.azuremonitor import AzureMonitorMetricsExporter
import logging


class AzureMonitorMetricsClient:
    """
    A client for creating and recording custom metrics in Azure Monitor using OpenTelemetry.
    """

    def __init__(self, connection_string: str, export_interval: int = 30):
        """
        Initializes the OpenTelemetry MeterProvider with the Azure Monitor exporter.

        Args:
            connection_string (str): The Azure Monitor connection string (Instrumentation Key).
            export_interval (int): The interval in seconds at which metrics are exported.
        """
        self.connection_string = connection_string
        self.export_interval = export_interval

        # Initialize the Azure Monitor exporter.
        self.exporter = AzureMonitorMetricsExporter(connection_string=self.connection_string)

        # Setup a periodic exporting reader.
        self.metric_reader = PeriodicExportingMetricReader(
            exporter=self.exporter,
            export_interval_millis=self.export_interval * 1000
        )

        # Setup the MeterProvider using the metric reader.
        self.meter_provider = MeterProvider(metric_readers=[self.metric_reader])
        metrics.set_meter_provider(self.meter_provider)
        self.meter = metrics.get_meter(__name__)

        # Dictionary to keep track of created instruments.
        self._instruments = {}
        logging.info("AzureMonitorMetricsClient initialized.")

    def create_counter(self, name: str, description: str = "", unit: str = "1"):
        """
        Creates and returns a counter instrument. If the counter already exists, it returns the existing one.

        Args:
            name (str): The name of the metric.
            description (str): A description of the metric.
            unit (str): The unit of the metric.

        Returns:
            A Counter instrument.
        """
        if name in self._instruments:
            return self._instruments[name]

        counter = self.meter.create_counter(name, description=description, unit=unit)
        self._instruments[name] = counter
        logging.info("Counter '%s' created.", name)
        return counter

    def record_metric(self, name: str, value: float, attributes: dict = None):
        """
        Records a metric value using the specified counter.

        Args:
            name (str): The name of the metric to record.
            value (float): The value to add.
            attributes (dict): A dictionary of attributes to associate with this metric value.
        """
        if name not in self._instruments:
            raise ValueError(f"Metric '{name}' not found. Please create it first using create_counter().")

        counter = self._instruments[name]
        if attributes is None:
            attributes = {}

        counter.add(value, attributes)
        logging.debug("Recorded %f to metric '%s' with attributes %s", value, name, attributes)