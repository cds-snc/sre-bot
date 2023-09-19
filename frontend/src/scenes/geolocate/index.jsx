import { Box } from "@mui/material";
import Header from "../../components/Header";

// Return a geolocate component. Right now it just displays the title and subtitle.
const Geolocate = () => {
  return (
    <Box m="20px">
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Header title="Geolocate an IP" subtitle="Geolocate a particular ip address"/>
                </Box>
            </Box>
)};

export default Geolocate;