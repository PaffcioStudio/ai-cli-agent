<script>
  let count = 0;
  const increment = () => count++;
</script>

<main>
  <h1>{{PROJECT_NAME}}</h1>
  <p>{{DESCRIPTION}}</p>

  <button on:click={increment}>
    Kliknięć: {count}
  </button>
</main>

<style>
  main {
    font-family: system-ui, sans-serif;
    max-width: 640px;
    margin: 4rem auto;
    padding: 0 1rem;
    text-align: center;
  }
  h1 { color: #ff3e00; }
  button {
    margin-top: 1rem;
    padding: .5rem 1.5rem;
    font-size: 1rem;
    border: none;
    border-radius: 6px;
    background: #ff3e00;
    color: white;
    cursor: pointer;
  }
</style>
