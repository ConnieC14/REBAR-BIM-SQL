import { useEffect, useState } from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faSearch } from "@fortawesome/free-solid-svg-icons";
import BotLoader from "./Loader";

interface Props {
  placeholder: string;
  nameID: string;
  addMessage: (text: string, sender: string) => void;
}

export default function Form({ placeholder, nameID, addMessage }: Props) {
  const [userInput, setUserInput] = useState({ [nameID]: "" });
  const [isLoading, setIsLoading] = useState(false);

  // Sends a welcome message on initial load
  useEffect(() => {
    addMessage("Hello! How can I help you today?", "bot");
  }, []);

  // Handles change in input field
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setUserInput({
      ...userInput,
      [event.target.name]: event.target.value,
    });
  };

  // Handles the form submission
  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    
    const userMessage = userInput[nameID];
    if (!userMessage.trim()) {
      addMessage("You haven't typed anything into the input field.", "bot");
      return;
    }

    // Add user message to chat and reset input
    addMessage(userMessage, "user");
    setUserInput({ [nameID]: "" });
    setIsLoading(true); // Start loading state

    // Log the request data before sending
    console.log("Sending data to backend:", { [nameID]: userMessage });
  
    try {
      // Send POST request to the backend
      const res = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ [nameID]: userMessage }),
      });

      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const data = await res.json();

      if (data.result) {
        addMessage(data.result, "bot");
      } else {
        addMessage(
          "I'm sorry, I didn't understand that. Could you please reword your question?",
          "bot"
        );
      }
    } catch (error) {
      console.log("Error:", error);
      addMessage("There was an error processing your request.", "bot");
    } finally {
      setIsLoading(false); // Stop loading state
    }
  };

  return (
    <form
      className="flex flex-row justify-center items-center w-full mt-4"
      onSubmit={handleSubmit}
    >
      <input
        className="w-[100%] h-[35px] ps-8 py-8 border-0 text-md bg-zinc-900 text-white"
        type="text"
        value={userInput[nameID]}
        name={nameID}
        placeholder={placeholder}
        onChange={handleChange}
      />
      <div className="input-group-append bg-zinc-900 h-[35px] text-sm py-8 flex px-8 items-center justify-center">
        <button type="submit">
          <div>
            <FontAwesomeIcon
              icon={faSearch}
              style={{ color: "white", width: "20px", height: "20px" }}
            />
          </div>
        </button>
      </div>

      {/* Show loading spinner when processing */}
      {isLoading && <BotLoader process="Processing your query..." />}
    </form>
  );
}
