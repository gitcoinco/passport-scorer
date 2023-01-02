import {
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
} from "@chakra-ui/react";

// Components
import { Icon } from "@chakra-ui/icons";
import { HiDotsVertical } from "react-icons/hi";

type MenuProps = {
  children?: Array<object>;
};

type menuChild = {
  label?: string;
  onClick?: () => void;
}

const MenuTemplate = ({children}: MenuProps): JSX.Element => {
  return (
    <>
      <Menu isLazy>
        <MenuButton className="rounded-md border border-gray-lightgray bg-white px-3 pt-1 pb-2 shadow-sm shadow-gray-100"
        >
          <Icon as={HiDotsVertical} color="#757087" />
        </MenuButton>
        <MenuList>
          {
            children?.map((child: menuChild) => {
              return (
                <MenuItem onClick={child.onClick}>{child.label}</MenuItem>
              );
            })
          }
        </MenuList>
      </Menu>
    </>
  )
};

export default MenuTemplate;
