// --- React components/methods
import React from "react";

type NoValuesProps = {
  addRequest: () => void;
  title: string;
  description: string;
  icon: JSX.Element;
  buttonText: string;
};

const NoValues = ({
  addRequest,
  title,
  description,
  icon,
  buttonText,
}: NoValuesProps): JSX.Element => {
  return (
    <div className="flex h-[38rem] flex-col justify-center md:h-[43rem]">
      <div className="w-13 mx-auto mb-8 flex justify-center rounded-full border bg-white p-2 text-center text-gray-lightgray">
        {icon}
      </div>
      <div className="mx-auto flex flex-col justify-center text-center align-middle">
        <h2 className="mx-auto font-miriamlibre text-xl text-blue-darkblue">
          {title}
        </h2>
        <p className="mx-auto mt-2 w-9/12 font-librefranklin text-purple-softpurple">
          {description}
        </p>
        <button
          onClick={addRequest}
          className="mx-auto mt-6 w-40 rounded-sm bg-purple-gitcoinviolet pt-1 pb-2 text-white"
        >
          <span className="text-xl">+</span>{buttonText}
        </button>
      </div>
    </div>
  );
};

export default NoValues;
