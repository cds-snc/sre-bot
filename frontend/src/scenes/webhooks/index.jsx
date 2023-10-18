import React, { useEffect, useState } from "react";
import { Box, List, ListItem, ListItemText, Typography } from "@mui/material";
import Header from "../../components/Header";

const Webhooks = () => {
  const [webhooks, setWebhooks] = useState([]);
  const apiUrl = `${window.origin}/list_webhooks`;

  useEffect(() => {
    // Fetch the list of webhooks from the API
    fetch(apiUrl)
      .then((response) => response.json())
      .then((data) => setWebhooks(data))
      .catch((error) => console.error("Error fetching webhooks:", error));
  }, []);

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="Webhooks" subtitle="Manage all webhooks here." />
      </Box>
      <Typography variant="h6" gutterBottom>
        Webhooks List
      </Typography>
      <List>
        {webhooks.map((webhook, index) => (
          <ListItem key={index}>
            <ListItemText
              primary={webhook.name.S}
              secondary={`Channel: ${webhook.channel.S}, Active: ${
                webhook.active.BOOL ? "Yes" : "No"
              }, Created At: ${webhook.created_at.S}`}
            />
          </ListItem>
        ))}
      </List>
    </Box>
  );
};

export default Webhooks;
