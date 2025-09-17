'use client';

import { useEffect, useState } from "react";
import {
  Box,
  Code,
  Divider,
  Stack,
  Text,
  Tooltip,
} from "@chakra-ui/react";

import { apiBaseUrl } from "../utils/constants";

const FALLBACK_VALUE = "unknown";

type BackendBuildInfo = {
  sha: string;
  sha_short: string;
  build_date: string;
};

type IndexOptionsResponse = {
  build_info?: BackendBuildInfo | null;
};

let backendBuildInfoPromise: Promise<BackendBuildInfo | null> | null = null;

function sanitize(value: string | undefined): string {
  if (!value) return FALLBACK_VALUE;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : FALLBACK_VALUE;
}

function getFrontendBuildInfo() {
  return {
    sha: sanitize(process.env.NEXT_PUBLIC_BUILD_SHA),
    sha_short: sanitize(process.env.NEXT_PUBLIC_BUILD_SHA_SHORT),
    build_date: sanitize(process.env.NEXT_PUBLIC_BUILD_DATE),
  };
}

async function fetchBackendBuildInfo(): Promise<BackendBuildInfo | null> {
  if (!backendBuildInfoPromise) {
    backendBuildInfoPromise = (async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/index-options`);
        if (!response.ok) {
          throw new Error(`Failed to load backend build info: ${response.status}`);
        }
        const data: IndexOptionsResponse = await response.json();
        const info = data.build_info;
        if (
          info &&
          typeof info.sha === "string" &&
          typeof info.sha_short === "string" &&
          typeof info.build_date === "string"
        ) {
          return info;
        }
      } catch (error) {
        console.warn("Unable to retrieve backend build metadata", error);
      }
      return null;
    })();
  }

  return backendBuildInfoPromise;
}

export function BuildInfoWidget() {
  const [backendInfo, setBackendInfo] = useState<BackendBuildInfo | null>();
  const frontendInfo = getFrontendBuildInfo();

  useEffect(() => {
    let mounted = true;
    fetchBackendBuildInfo().then((info) => {
      if (mounted) setBackendInfo(info);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const backend = backendInfo ?? null;

  return (
    <Tooltip
      label={
        <Stack spacing={2} fontSize="sm">
          <Box>
            <Text fontWeight="bold" mb={1}>
              Frontend
            </Text>
            <Text>
              SHA: <Code>{frontendInfo.sha_short}</Code>
            </Text>
            <Text>
              Full SHA: <Code>{frontendInfo.sha}</Code>
            </Text>
            <Text>Built: {frontendInfo.build_date}</Text>
          </Box>
          <Divider borderColor="whiteAlpha.400" />
          <Box>
            <Text fontWeight="bold" mb={1}>
              Backend
            </Text>
            <Text>
              SHA: <Code>{sanitize(backend?.sha_short)}</Code>
            </Text>
            <Text>
              Full SHA: <Code>{sanitize(backend?.sha)}</Code>
            </Text>
            <Text>Built: {sanitize(backend?.build_date)}</Text>
          </Box>
        </Stack>
      }
      placement="top-end"
      hasArrow
      openDelay={0}
      closeDelay={0}
    >
      <Box
        position="fixed"
        bottom={{ base: 4, md: 6 }}
        right={{ base: 4, md: 6 }}
        zIndex={1400}
        bg="gray.500"
        color="white"
        px={2}
        py={1.5}
        fontSize="sm"
        borderRadius="full"
        boxShadow="lg"
        opacity={0.75}
        _hover={{ opacity: 1.0 }}
        _focusVisible={{ outline: "2px solid", outlineColor: "gray.200" }}
      >
        v1
      </Box>
    </Tooltip>
  );
}

export function __resetBackendBuildInfoCacheForTests() {
  backendBuildInfoPromise = null;
}

export default BuildInfoWidget;
