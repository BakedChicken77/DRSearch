"use client";

import React, { useState } from "react";
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
  Button,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  ModalFooter,
  Select,
  Text,
  VStack,
  Spinner,
} from "@chakra-ui/react";
import { SettingsIcon } from "@chakra-ui/icons";
import { fetchDocumentList } from "../utils/fetchDocumentList";

export function SettingsDrawer({
  numDocs,
  setNumDocs,
  indexOptions,
  token,
}: {
  numDocs: number;
  setNumDocs: (v: number) => void;
  indexOptions: { name: string; display_name: string }[] | null;
  token?: string;
}) {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const {
    isOpen: modalOpen,
    onOpen: openModal,
    onClose: closeModal,
  } = useDisclosure();
  const [selectedIndex, setSelectedIndex] = useState("");
  const [docs, setDocs] = useState<string[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
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
            <Button
              mt={4}
              onClick={openModal}
              isDisabled={(indexOptions?.length ?? 0) === 0}
            >
              Get Document List
            </Button>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
      <Modal isOpen={modalOpen} onClose={closeModal} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Documents</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Select
              placeholder="Select Index"
              mb={4}
              value={selectedIndex}
              onChange={(e) => setSelectedIndex(e.target.value)}
            >
              {indexOptions?.map((o) => (
                <option key={o.name} value={o.name}>
                  {o.display_name}
                </option>
              ))}
            </Select>
            {loadingDocs ? (
              <Spinner />
            ) : (
              <VStack align="start" spacing={1} maxH="300px" overflowY="auto">
                {docs.map((d) => (
                  <Text key={d}>{d}</Text>
                ))}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button
              mr={3}
              onClick={async () => {
                if (!selectedIndex) return;
                setLoadingDocs(true);
                try {
                  const list = await fetchDocumentList(selectedIndex, token);
                  setDocs(list);
                } catch (e: any) {
                  console.error(e);
                } finally {
                  setLoadingDocs(false);
                }
              }}
            >
              Fetch
            </Button>
            <Button onClick={closeModal}>Close</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  );
}
