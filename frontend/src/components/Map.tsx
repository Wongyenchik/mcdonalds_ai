import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import api from "../api";

// Fix for default marker icons in React-Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require("leaflet/dist/images/marker-icon-2x.png"),
  iconUrl: require("leaflet/dist/images/marker-icon.png"),
  shadowUrl: require("leaflet/dist/images/marker-shadow.png"),
});

interface Outlet {
  id: number;
  name: string;
  address: string;
  latitude: number;
  longitude: number;
  telephone: string;
  waze_link: string;
}

const Map: React.FC = () => {
  const [outlets, setOutlets] = useState<Outlet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchOutlets = async () => {
      try {
        const response = await api.get<Outlet[]>("/outlets");
        setOutlets(response.data);
      } catch (err) {
        setError("Failed to fetch outlets data");
        console.error("Error fetching outlets:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchOutlets();
  }, []);

  const center =
    outlets.length > 0
      ? [outlets[0].latitude, outlets[0].longitude]
      : [3.139, 101.6869]; // Default to Kuala Lumpur coordinates

  if (loading) return <div className="map-loading">Loading map...</div>;
  if (error) return <div className="map-error">Error: {error}</div>;

  return (
    <MapContainer
      center={center as [number, number]}
      zoom={11}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      />
      {outlets.map((outlet) => (
        <React.Fragment key={outlet.id}>
          <Marker position={[outlet.latitude, outlet.longitude]}>
            <Popup>
              <div>
                <h3>{outlet.name}</h3>
                <p>{outlet.address}</p>
                <br></br>
                <p>{outlet.telephone}</p>
                <br></br>
                <a
                  href={outlet.waze_link}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <p>Waze</p>
                </a>
              </div>
            </Popup>
          </Marker>
          <Circle
            center={[outlet.latitude, outlet.longitude]}
            radius={5000} // 5KM in meters
            pathOptions={{
              color: "blue",
              fillColor: "blue",
              fillOpacity: 0.1,
              weight: 1,
            }}
          />
        </React.Fragment>
      ))}
    </MapContainer>
  );
};

export default Map;
