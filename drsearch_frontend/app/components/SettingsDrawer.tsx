"use client";

import React from "react";
import {
  Drawer,
  DrawerOverlay,
  DrawerContent,
  DrawerHeader,
  DrawerBody,
  DrawerCloseButton,
  IconButton,
  useDisclosure,
  FormControl,
  FormLabel,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
} from "@chakra-ui/react";
import { SettingsIcon } from "@chakra-ui/icons";

export function SettingsDrawer({
  numDocs,
  setNumDocs,
}: {
  numDocs: number;
  setNumDocs: (v: number) => void;
}) {
  const { isOpen, onOpen, onClose } = useDisclosure();
  return (
    <>
      <IconButton
        aria-label="Open settings"
        icon={<SettingsIcon />}
        position="absolute"
        top={2}
        left={2}
        onClick={onOpen}
      />
      <Drawer placement="left" onClose={onClose} isOpen={isOpen} size="xs">
        <DrawerOverlay />
        <DrawerContent>
          <DrawerCloseButton />
          <DrawerHeader>Settings</DrawerHeader>
          <DrawerBody>
            <FormControl>
              <FormLabel>Documents to retrieve</FormLabel>
              <NumberInput
                min={1}
                max={5}
                value={numDocs}
                onChange={(_s, v) => setNumDocs(v)}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
            </FormControl>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </>
  );
}
