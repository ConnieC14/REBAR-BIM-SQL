interface LoaderProps {
  process: string;
}

const BotLoader: React.FC<LoaderProps> = ({ process }) => {
  return (
    <>
    <div className="process-bubble">{process}</div>
    </>
  );
};

export default BotLoader;
