import { Box } from "@mui/material";
import Header from "../../components/Header";

// Setup the webhooks component. Right now it just displays the title and subtitle.
const Webhooks= () => {
  return (
    <Box m="20px">
                <Box display="flex" justifyContent="space-between" alignItems="center">
                    <Header title="Webhooks" subtitle="Manage all webhooks here."/>
                </Box>
            </Box>
)};

export default Webhooks;