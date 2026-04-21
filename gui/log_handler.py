"""
Module de redirection des logs vers la console graphique de la GUI.

Problème résolu : le pipeline utilise `logging.getLogger()` standard.
Pour afficher ces logs en temps réel dans la fenêtre Tkinter, on crée
un `logging.Handler` personnalisé qui place chaque enregistrement dans
une `queue.Queue` thread-safe.

La GUI lit ensuite cette queue toutes les 100 ms via `widget.after()`.
"""

import logging
import queue


class GUILogHandler(logging.Handler):
    """
    Handler de logging qui redirige les enregistrements vers une queue partagée.

    Cette queue est consommée par la boucle principale de l'interface graphique
    (méthode `_poll_log_queue` dans `app.py`) pour afficher les messages en
    temps réel dans la console de log sans bloquer le thread principal.

    Usage typique :
        log_queue = queue.Queue()
        handler = GUILogHandler(log_queue)
        logging.getLogger().addHandler(handler)
    """

    def __init__(self, log_queue: queue.Queue) -> None:
        """
        Initialise le handler avec la queue partagée.

        Args:
            log_queue: Queue dans laquelle seront placés les messages formatés.
        """
        super().__init__()
        self.log_queue = log_queue

        # Formateur lisible : heure + niveau + message
        formatter = logging.Formatter("%(asctime)s  [%(levelname)s]  %(message)s",
                                      datefmt="%H:%M:%S")
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        """
        Appelé automatiquement par le système de logging pour chaque enregistrement.

        Formate le message et l'envoie dans la queue sous la forme d'un tuple
        (niveau, texte_formaté) afin que la GUI puisse appliquer une couleur
        différente selon le niveau.

        Args:
            record: Enregistrement de log brut fourni par le framework logging.
        """
        try:
            # Formatage du message (applique le pattern défini dans __init__)
            msg = self.format(record)
            # On envoie un tuple (niveau, message) pour le coloriage dans la GUI
            self.log_queue.put_nowait((record.levelname, msg))
        except Exception:
            # En cas d'erreur de formatage on ne plante pas l'application
            self.handleError(record)
