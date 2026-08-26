# Do currículo em PDF ao Career OS: como construí um sistema para gerenciar minha trajetória profissional

Durante muito tempo, tratei meu currículo como a maioria das pessoas trata: um documento que eu atualizava quando aparecia uma oportunidade.

O processo parecia simples. Eu abria a versão mais recente, mudava o resumo, reorganizava algumas experiências, ajustava palavras-chave e salvava outro arquivo com um nome parecido com `curriculo_final_v2.pdf`.

Funcionava, mas havia um problema crescente: quanto mais vagas eu analisava, mais versões do meu próprio histórico eu criava.

Uma destacava Product Management. Outra priorizava Growth. Uma terceira tentava traduzir minha experiência para Go-to-Market, Sales Enablement ou implementação de IA. Em português e inglês, o número de combinações aumentava ainda mais.

As informações eram verdadeiras, mas estavam espalhadas. Uma métrica atualizada em um documento continuava antiga nos demais. Um case relevante desaparecia porque não cabia em determinada versão. E, a cada nova candidatura, eu precisava reconstruir o raciocínio: quais experiências realmente provam que tenho aderência a esta vaga?

Foi quando percebi que o problema não era escrever um currículo melhor.

O problema era tratar uma trajetória profissional inteira como um arquivo de texto.

## O currículo é uma visualização, não a fonte

Um PDF é uma boa interface de entrega. É portátil, legível e aceito por praticamente qualquer processo seletivo. Mas é uma estrutura ruim para armazenar conhecimento profissional.

Uma carreira contém muito mais do que cabe em duas páginas:

- experiências e responsabilidades;
- projetos e cases;
- competências demonstradas;
- ferramentas utilizadas;
- métricas e resultados;
- diferentes formas de descrever a mesma conquista;
- relações entre problemas, ações e impactos;
- evidências que sustentam cada afirmação.

O PDF deveria ser apenas uma das possíveis visualizações desse conjunto de dados.

A partir dessa mudança de perspectiva, comecei a construir o que hoje chamo de **Career OS**: um sistema pessoal para organizar, relacionar e ativar meu histórico profissional de acordo com cada oportunidade.

Em vez de manter vários currículos como fontes independentes, passei a ter uma fonte única de verdade: um currículo mestre estruturado em JSON, com informações em português e inglês.

O princípio é simples:

> Minha trajetória permanece estável. O que muda para cada vaga é a seleção e a apresentação das evidências mais relevantes.

## Da descrição da vaga a uma decisão de posicionamento

O sistema não começa escrevendo. Ele começa interpretando a oportunidade.

Ao receber uma descrição de vaga, o fluxo extrai e organiza informações como cargo, empresa, localização, modalidade, responsabilidades, requisitos, idioma e remuneração, quando disponível.

Depois, realiza uma triagem:

- quais requisitos possuem evidência direta no meu histórico;
- quais podem ser atendidos por competências transferíveis;
- quais representam lacunas reais;
- quais experiências e resultados melhor sustentam meu posicionamento;
- quais riscos ou incompatibilidades precisam ser considerados.

Só então começa a adaptação.

O resultado não é apenas um currículo. Para cada vaga, o sistema cria um artefato versionado com:

- análise de aderência;
- pontos fortes e lacunas;
- currículo em português;
- currículo em inglês;
- carta de apresentação nos dois idiomas;
- respostas prováveis para formulários de candidatura;
- lista das competências utilizadas como evidência.

Esses materiais são validados, ativados e publicados em uma aplicação local feita com Streamlit, onde posso revisar o conteúdo e exportar o currículo em HTML ou PDF.

O fluxo completo passou a ser:

**vaga → triagem → evidências → adaptação → validação → revisão → exportação**

Essa ordem importa. Quando a geração de texto vem antes da estruturação das evidências, a fluência pode esconder inconsistências.

## O desafio não era gerar texto

Modelos de linguagem escrevem resumos e cartas de apresentação com facilidade. O desafio real é garantir que um texto convincente continue sendo verdadeiro.

Em um currículo, uma pequena extrapolação pode mudar completamente o significado de uma experiência. Ter utilizado uma competência relacionada não significa possuir experiência direta em uma ferramenta. Ter participado de um projeto não significa tê-lo liderado. Um resultado do time não pode ser automaticamente apresentado como resultado individual.

Por isso, defini algumas regras para o sistema:

1. Nenhuma experiência, empresa, cargo, ferramenta, métrica ou resultado pode ser inventado.
2. As competências declaradas precisam existir literalmente na fonte mestre.
3. A adaptação pode mudar ênfase e linguagem, mas não os fatos.
4. Competência transferível deve ser apresentada como transferível, não como experiência direta.
5. Lacunas relevantes devem aparecer na análise e, quando necessário, nas respostas de candidatura.

Também criei validações automáticas. O sistema verifica, por exemplo, se os dois idiomas foram produzidos, se a carta menciona corretamente a empresa-alvo e se as competências utilizadas pertencem ao repertório comprovado.

Essas restrições não reduzem a utilidade da IA. Elas tornam a IA mais útil, porque deslocam seu papel de “inventora de uma versão ideal do candidato” para “editora estratégica de evidências reais”.

## Quando o currículo virou um grafo

A estrutura em JSON resolveu a fonte única de verdade, mas ainda havia outra questão: como encontrar as melhores evidências para cada vaga sem enviar todo o histórico para o modelo?

A resposta foi transformar parte da trajetória em um grafo de conhecimento.

Nesse grafo, experiências se conectam a conquistas. Conquistas demonstram competências, utilizam ferramentas e produzem métricas. Vagas possuem requisitos, e esses requisitos são associados às competências necessárias.

Em termos simplificados:

**experiência → conquista → competência → requisito da vaga**

Essa estrutura permite recuperar apenas o subgrafo relevante para uma oportunidade. Em vez de pedir que a IA procure sinais em todo o currículo, o sistema pode entregar um contexto menor e mais preciso, contendo:

- os requisitos prioritários;
- as competências e ferramentas relacionadas;
- as conquistas mais aderentes;
- as métricas que comprovam impacto;
- os caminhos de transferibilidade entre competências.

O sistema também usa relações entre skills para analisar proximidade. Uma competência pode ser uma especialização de outra ou estar relacionada a uma capacidade mais ampla. Com isso, consigo diferenciar correspondência direta, aderência transferível e lacuna real.

Isso não serve para “forçar” um match. Serve para tornar o raciocínio explícito.

Se uma vaga pede algo que eu nunca fiz, o sistema deve dizer isso. Se existe uma experiência próxima, ele deve mostrar qual é a conexão e com que nível de confiança ela pode ser defendida.

## Um produto pessoal também exige decisões de produto

Construir uma ferramenta para mim mesmo eliminou a distância entre usuário e desenvolvedor. Cada falha aparecia no uso real.

Descobri, por exemplo, que não bastava gerar uma nova adaptação. Era necessário garantir que a interface invalidasse os dados da vaga anterior. Não bastava manter versões em dois idiomas; era preciso impedir que português e inglês ficassem dessincronizados. Não bastava salvar arquivos; era necessário saber qual vaga estava ativa e preservar um histórico versionado.

Esses problemas são menos chamativos do que uma demonstração de IA, mas são justamente o que separa uma prova de conceito de um produto utilizável.

O projeto passou a combinar diferentes disciplinas:

- Product Management para definir o problema e priorizar o fluxo;
- arquitetura da informação para organizar a fonte mestre;
- engenharia de dados para estruturar relações e evidências;
- IA generativa para adaptar a comunicação;
- regras determinísticas para validar o resultado;
- UX para permitir revisão e exportação;
- governança para reduzir alucinações e preservar rastreabilidade.

No fim, o valor não está em automatizar a escrita de um currículo. Está em reduzir o custo cognitivo de interpretar a própria trajetória toda vez que uma nova oportunidade aparece.

## O que mudou na forma como vejo minha carreira

Antes, eu enxergava minhas experiências como blocos separados no tempo. Ao estruturar os dados e construir as relações, comecei a perceber continuidades que um currículo cronológico não mostrava com clareza.

Projetos diferentes revelavam padrões recorrentes: validação de produtos, construção de operações, uso de dados, automação, aquisição, capacitação e implementação de IA. O grafo não criou essas competências. Ele apenas tornou visíveis conexões que já existiam.

Essa talvez tenha sido a descoberta mais valiosa do projeto.

Organizar uma carreira não é apenas registrar o que aconteceu. É construir uma forma confiável de consultar o que foi aprendido, onde foi aplicado e quais resultados foram produzidos.

Hoje, quando encontro uma vaga, não começo perguntando “como posso parecer adequado para ela?”.

Começo com perguntas melhores:

- Quais problemas dessa empresa eu já ajudei a resolver em outros contextos?
- Que evidências sustentam essa afirmação?
- Onde existe transferibilidade legítima?
- Quais lacunas eu preciso reconhecer?
- Vale a pena me candidatar?

O currículo continua existindo. Mas agora ele é a saída de um sistema, não o sistema inteiro.

E essa mudança, de documento para infraestrutura pessoal de carreira, transformou não apenas a forma como preparo candidaturas, mas também a forma como compreendo e comunico meu próprio trabalho.

## Experimente o meu Career OS

O projeto está disponível online para quem quiser conhecer a experiência e visualizar como essa abordagem funciona na prática:

**[Acesse e experimente o meu Career OS](https://keevinvieeira.github.io/curriculo-kevin/)**

---

**Kevin Augusto Vieira**  
Product Manager e GTM Specialist, com foco em produtos digitais, automação, dados e implementação de IA.
