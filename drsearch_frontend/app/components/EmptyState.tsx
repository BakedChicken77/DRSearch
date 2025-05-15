// app\components\EmptyState.tsx

import { MouseEvent } from "react";
import {
  Heading,
  Card,
  CardHeader,
  Flex,
  VStack,
  Select,
  Spinner,
} from "@chakra-ui/react";
import { Image } from "@chakra-ui/react";
import { IndexOption } from "../utils/fetchIndexOptions";

const iconSrc = "llama_cafe.ico";

export function EmptyState(props: {
  onChoice: (question: string) => any;
  selectedIndexName: string;
  setSelectedIndexName: React.Dispatch<React.SetStateAction<string>>;
  indexOptions: IndexOption[] | null;
  loadingOptions: boolean;
}) {
  const {
    onChoice,
    selectedIndexName,
    setSelectedIndexName,
    indexOptions,
    loadingOptions,
  } = props;

  if (loadingOptions)
    return (
      <VStack pt={20}>
        <Spinner size="xl" />
      </VStack>
    );

  const current = indexOptions?.find((o) => o.name === selectedIndexName);

  return (
    <div className="rounded flex flex-col items-center max-w-full md:p-8 relative">
      {/* Uncomment and adjust the Image component if you want to include an icon */}
      {/*
      <Image 
        src={iconSrc} 
        alt="My Icon" 
        style={{ 
          width: '500px',
          height: '500px',
          position: 'absolute',
          left: '300px',
          top: '300px',
          objectFit: 'cover'
        }} 
        className="absolute inset-0 object-cover" 
      />
      */}

      <div className="relative z-10">
        <VStack spacing={4} align="center" maxWidth="800px" width="100%">
          <Heading fontSize="8xl" fontWeight={"medium"} mb={1} color={"black"}>
            DRS ASSISTANT
          </Heading>
          <p style={{ color: "black", textAlign: "center" }}>
            Here to assist
          </p>
          <Select
            value={selectedIndexName}
            onChange={(e) => setSelectedIndexName(e.target.value)}
            placeholder="Select Document Index"
            marginBottom="20px"
            width="100%"
          >
            {indexOptions?.map((opt) => (
              <option key={opt.name} value={opt.name}>
                {opt.display_name}
              </option>
            ))}
          </Select>
        </VStack>

        {current && (
          <Flex
            direction="row"
            wrap="wrap"
            marginTop={"50px"}
            grow={1}
            maxWidth={"800px"}
            width={"100%"}
            justifyContent="space-between"
          >
            {current.example_questions.map((q, idx) => (
              <Card
                key={idx}
                onMouseUp={selectedIndexName ? () => onChoice(q) : undefined}
                width={"48%"}
                backgroundColor={
                  selectedIndexName ? "rgb(58, 58, 61)" : "gray.300"
                }
                _hover={
                  selectedIndexName
                    ? { backgroundColor: "rgb(78,78,81)" }
                    : {}
                }
                cursor={selectedIndexName ? "pointer" : "not-allowed"}
                marginBottom="25px"
                marginTop={idx >= 2 ? "25px" : "0"}
              >
                <CardHeader>
                  <Heading
                    fontSize="lg"
                    fontWeight={"medium"}
                    color={selectedIndexName ? "gray.200" : "gray.500"}
                    textAlign={"center"}
                  >
                    {q}
                  </Heading>
                </CardHeader>
              </Card>
            ))}
          </Flex>
        )}
      </div>
    </div>
  );
}