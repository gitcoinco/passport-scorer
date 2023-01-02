import React from "react";

import {
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverBody,
} from "@chakra-ui/react";

type PopoverProps = {
  text?: string;
};

const PopoverTemplate = ({text}: PopoverProps): JSX.Element => {
  return (
    <>
      <Popover>
        <PopoverContent>
          <PopoverBody>
            {text}
          </PopoverBody>
        </PopoverContent>
      </Popover>
    </>
  );
};

export default PopoverTemplate;
