# Perguntas para definir o backup e a recuperação

Este questionário fecha somente decisões de uso da issue #44. Ele **não pede o
código de recuperação**, senha, documento, nome de cliente, número de série do
HD ou qualquer outro dado real. Não envie esses itens por chat, issue ou GitHub.

Já está confirmado que o backup será feito em HD externo e deverá permitir a
restauração depois da perda ou troca do computador.

## 1. Rotina de backup

1. Com que frequência o aplicativo deve lembrar de fazer backup?
   - [ ] todo dia útil;
   - [ ] uma vez por semana;
   - [ ] outra frequência: ________________________________________________
2. O backup será iniciado manualmente pelo proprietário após o lembrete?
   - [ ] sim;
   - [ ] não — comportamento esperado: ___________________________________
3. Em qual período costuma ser mais conveniente bloquear o CRM por alguns
   minutos para criar o backup? ___________________________________________
4. Se o HD não estiver conectado, o aplicativo deve apenas manter o lembrete e
   tentar novamente somente após confirmação?
   - [ ] sim;
   - [ ] não — comportamento esperado: ___________________________________

O MVP não executará backup escondido nem conectará sozinho a nuvem ou rede.

## 2. HD externo e histórico

1. Quantos HDs serão usados em rotação?
   - [ ] um;
   - [ ] dois ou mais;
   - [ ] ainda não definido.
2. O HD já existe?
   - [ ] sim;
   - [ ] ainda será comprado/escolhido.
3. O proprietário aceita que o aplicativo recuse FAT32, rede, pasta sincronizada
   e o mesmo disco do computador, sem formatar o HD automaticamente?
   - [ ] sim;
   - [ ] não — motivo: ___________________________________________________
4. Como não existe prazo de descarte aprovado, o comportamento seguro proposto
   é **nunca apagar nem sobrescrever backup anterior automaticamente**. Quando o
   espaço terminar, o CRM pedirá outro HD ou uma decisão externa documentada.
   - [ ] aprovado;
   - [ ] quero outra regra: _______________________________________________

Não informe marca, serial, nome do volume ou caminho real neste documento.

## 3. Código de recuperação

O CRM gerará um código forte. Ele não será escolhido pelo usuário. Sem esse
código, o backup criptografado não poderá ser restaurado em outro computador.

1. Onde será guardada a cópia separada do computador e do HD?
   - [ ] folha impressa em local físico protegido;
   - [ ] gerenciador de senhas confiável;
   - [ ] outra forma separada: ____________________________________________
2. Quem será responsável por conferir periodicamente essa guarda? Informe
   somente o papel, sem nome pessoal: _____________________________________
3. Para facilitar backups rotineiros, o aplicativo pode guardar uma cópia local
   protegida pelo Windows, sabendo que a cópia portátil continuará separada?
   - [ ] sim; não quero digitar o código em todo backup;
   - [ ] não; prefiro informar o código a cada backup;
   - [ ] preciso de uma demonstração antes de decidir.
4. O aplicativo pode permitir reexibir/imprimir novamente o código após login e
   confirmação explícita do proprietário?
   - [ ] sim;
   - [ ] não;
   - [ ] preciso de uma demonstração antes de decidir.
5. Em caso de suspeita de exposição do código, o comportamento proposto é gerar
   outro código e um novo backup completo. Backups antigos continuarão exigindo
   o código antigo e não serão apagados automaticamente.
   - [ ] aprovado;
   - [ ] quero outra regra: _______________________________________________

Nunca escreva o código real nas respostas deste questionário.

## 4. Restauração e teste periódico

1. Depois de restaurar em outro computador, o proprietário prefere:
   - [ ] informar a senha atual do CRM;
   - [ ] criar uma nova senha após o backup e o código serem autenticados;
   - [ ] preciso de uma demonstração antes de decidir.
2. A restauração deve ser um assistente guiado que não exige terminal?
   - [ ] sim;
   - [ ] não — comportamento esperado: ___________________________________
3. Quem pode autorizar a restauração sobre uma instalação que já possui dados?
   Informe somente o papel: ______________________________________________
4. Com que frequência deve ser feito um teste de restauração usando somente
   dados sintéticos ou uma cópia de teste protegida?
   - [ ] mensal;
   - [ ] trimestral;
   - [ ] semestral;
   - [ ] outra frequência: ________________________________________________
5. Após cada backup, o aplicativo pedirá ejeção segura, reconexão do HD e
   verificação completa antes de mostrar **backup verificado**.
   - [ ] aprovado;
   - [ ] quero outra regra: _______________________________________________

## 5. Confirmação

- [ ] Entendo que guardar o código somente no computador ou junto do HD não
      atende à recuperação após perda/roubo.
- [ ] Entendo que perder simultaneamente o código e o computador torna o backup
      irrecuperável.
- [ ] Entendo que o aplicativo não formatará o HD nem apagará backups antigos
      automaticamente.
- [ ] Confirmo que nenhuma resposta contém segredo ou dado real.

- **Papel/identificador não pessoal de quem aprovou:** ______________________
- **Data (dia/mês/ano):** _________________________________________________
- **Ressalvas:** nenhuma / _________________________________________________

Qualquer resposta vazia ou “ainda não definido” mantém somente a decisão
relacionada bloqueada; o time não completará a lacuna por hipótese.
