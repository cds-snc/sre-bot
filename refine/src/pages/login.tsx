import { useLogin } from "@refinedev/core";
import { useEffect, useRef } from "react";

import { Box, Space, Text } from "@mantine/core";
import { ThemedTitleV2 } from "@refinedev/mantine";

import { CredentialResponse } from "../interfaces/google";

import { AppIcon } from "../components/app-icon";

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
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <ThemedTitleV2
        collapsed={false}
        wrapperStyles={{
          fontSize: "22px",
        }}
        text="refine Project"
        icon={<AppIcon />}
      />
      <Space h="xl" />

      <GoogleButton />

      <Space h="xl" />
      <Text fz="sm" color="gray">
        Powered by
        <img
          style={{ padding: "0 5px" }}
          alt="Google"
          src="https://refine.ams3.cdn.digitaloceanspaces.com/superplate-auth-icons%2Fgoogle.svg"
        />
        Google
      </Text>
    </Box>
  );
};
