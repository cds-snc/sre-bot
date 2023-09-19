import { useCustom, CustomResponse } from "@refinedev/core";
import { Box, TextInput, Button, Table } from "@mantine/core";
import { useState } from "react";

interface GeolocateResponse {
  country: string | null;
  city: string | null;
  latitude: number | null;
  longitude: number | null;
}

export const Geolocate: React.FC = () => {
  const [ip, setIp] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState<GeolocateResponse | null>(null);

  const handleButtonClick = async () => {
    setIsLoading(true);
    const response = await fetch(
      `https://sre-bot.cdssandbox.xyz/geolocate/${ip}`
    );
    const json = await response.json();
    setData(json.data);
    setIsLoading(false);
  };

  return (
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <TextInput
        label="IP Address"
        value={ip}
        onChange={(event) => setIp(event.currentTarget.value)}
      />
      <Button onClick={handleButtonClick} disabled={isLoading}>
        {isLoading ? "Loading..." : "Submit"}
      </Button>
      {data ? (
        <Table>
          <thead>
            <tr>
              <th>Country</th>
              <th>City</th>
              <th>Latitude</th>
              <th>Longitude</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>{data.country ?? "null"}</td>
              <td>{data.city ?? "null"}</td>
              <td>{data.latitude ?? "null"}</td>
              <td>{data.longitude ?? "null"}</td>
            </tr>
          </tbody>
        </Table>
      ) : null}
    </Box>
  );
};
