import { useLogin } from "@refinedev/core";
import { useEffect, useRef } from "react";

import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Typography from "@mui/material/Typography";
import { ThemedTitleV2 } from "@refinedev/mui";

import { CredentialResponse } from "../interfaces/google";

import sre_bot_logo from "../assets/sre_bot_logo.png";
// Todo: Update your Google Client ID here
const GOOGLE_CLIENT_ID =
  "216196914678-8q2rt8u8342igcue61fod5h5g6gcncqc.apps.googleusercontent.com";

export const Login: React.FC = () => {
  const { mutate: login } = useLogin<CredentialResponse>();

  const GoogleButton = (): JSX.Element => {
    const divRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
      if (typeof window === "undefined" || !window.google || !divRef.current) {
        return;
      }

      try {
        window.google.accounts.id.initialize({
          ux_mode: "popup",
          client_id: GOOGLE_CLIENT_ID,
          callback: async (res: CredentialResponse) => {
            if (res.credential) {
              login(res);
            }
          },
        });
        window.google.accounts.id.renderButton(divRef.current, {
          theme: "filled_blue",
          size: "medium",
          type: "standard",
        });
      } catch (error) {
        console.log(error);
      }
    }, []);

    return <div ref={divRef} />;
  };

  return (
    <Box className="hero" sx={{ minHeight: "100vh", bgcolor: "primary.main" }}>
      <Container
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          height: "100%",
        }}
      >
        <Box
          sx={{
            width: { xs: "100%", lg: "auto" },
            height: { xs: "auto", lg: "100%" },
            mb: { xs: 4, lg: 0 },
          }}
        >
          <Box sx={{ ml: { xs: 0, lg: 4 } }}>
            <img
              src={sre_bot_logo}
              alt="sre_bot"
              style={{ width: "25%", height: "25%" }}
            />

            {/* <ThemedTitleV2
          collapsed={false}
          wrapperStyles={{
            fontSize: "22px",
            justifyContent: "center",
          }}
        /> */}
            <Typography
              variant="h1"
              sx={{
                fontSize: { xs: "4rem", lg: "5rem" },
                fontWeight: "bold",
                mb: 4,
              }}
            >
              Welcome!
            </Typography>
            <Typography
              variant="body1"
              sx={{ fontSize: { xs: "1.5rem", lg: "1.75rem" }, mb: 4 }}
            >
              Log into the SRE bot by pressing the button below
            </Typography>
            <GoogleButton />
          </Box>
        </Box>
      </Container>
    </Box>
  );
};
